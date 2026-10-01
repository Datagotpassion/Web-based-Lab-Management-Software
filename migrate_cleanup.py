"""Retire the legacy location tables now that the container tree drives the app.

Why
---
After migrate_containers.py and the structure editor, the database held two
parallel location models: the live storage_units / storage_containers tree, and
five legacy tables that nothing reads any more (fridge_config, fridge_layouts,
fridge_regions, fridge_schematic_layouts, fridge_schematic_zones) plus the
legacy fridges table. Keeping both is exactly the confusion the container tree
was meant to end -- two places to add a fridge, two notions of where a reagent
lives -- so the legacy side goes.

What is preserved
-----------------
The reference photos of the -20 C fridge are associated with a fridge section
only inside fridge_schematic_layouts. Dropping that table would leave the image
files on disk with nothing recording which fridge or section they belong to, so
they are carried onto the matching section container first.

storage_containers.legacy_zone_id already records which old zone each container
came from, and backups/csv/ holds every legacy table as text under version
control, so this stays recoverable.

Usage
-----
    python migrate_cleanup.py            # dry run, reports what would change
    python migrate_cleanup.py --apply    # write it
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).parent / 'lab_management.db'

LEGACY_TABLES = (
    'fridge_schematic_zones',
    'fridge_schematic_layouts',
    'fridge_regions',
    'fridge_layouts',
    'fridge_config',
    'fridges',
)

# Columns on drugs that the body/door grid needed and nothing reads now.
LEGACY_DRUG_COLUMNS = (
    'storage_section',
    'storage_row',
    'storage_column',
    'fridge_region_id',
)

# Same, on the antibody tables.
LEGACY_ANTIBODY_COLUMNS = ('fridge_region_id',)


def table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]


def plan_photo_carry(conn):
    """Match each legacy layout's reference photo to its section container."""
    if not table_exists(conn, 'fridge_schematic_layouts'):
        return []
    carries = []
    rows = conn.execute(
        'SELECT id, fridge_id, section, reference_photo FROM '
        'fridge_schematic_layouts WHERE reference_photo IS NOT NULL').fetchall()
    for row in rows:
        # The section containers were created from these layouts, labelled
        # Body / Door, so match on unit plus label.
        target = conn.execute(
            'SELECT id, label FROM storage_containers WHERE unit_id = ? '
            "AND parent_id IS NULL AND LOWER(label) = LOWER(?)",
            (row['fridge_id'], row['section'])).fetchone()
        carries.append({
            'photo': row['reference_photo'],
            'unit_id': row['fridge_id'],
            'section': row['section'],
            'container_id': target['id'] if target else None,
            'container_label': target['label'] if target else None,
        })
    return carries


def report(conn, carries):
    print('=' * 72)
    print('CLEANUP PLAN')
    print('=' * 72)

    print('\nReference photos to carry onto the container tree:')
    if not carries:
        print('   (none recorded)')
    for c in carries:
        if c['container_id']:
            print(f"   {c['photo']}  ->  container #{c['container_id']} "
                  f"({c['container_label']})")
        else:
            print(f"   {c['photo']}  ->  NO MATCHING CONTAINER "
                  f"(unit {c['unit_id']}, section {c['section']}) - will be skipped")

    print('\nLegacy tables to drop:')
    for t in LEGACY_TABLES:
        if table_exists(conn, t):
            n = conn.execute(f'SELECT COUNT(*) c FROM "{t}"').fetchone()['c']
            print(f'   {t:<30} {n:>4} rows')
        else:
            print(f'   {t:<30}  already gone')

    print('\nLegacy columns to drop:')
    for table, cols in (('drugs', LEGACY_DRUG_COLUMNS),
                        ('primary_antibodies', LEGACY_ANTIBODY_COLUMNS),
                        ('secondary_antibodies', LEGACY_ANTIBODY_COLUMNS)):
        if not table_exists(conn, table):
            continue
        present = columns(conn, table)
        for col in cols:
            if col not in present:
                print(f'   {table}.{col:<22}  already gone')
                continue
            n = conn.execute(
                f'SELECT COUNT(*) c FROM "{table}" WHERE "{col}" IS NOT NULL'
            ).fetchone()['c']
            note = '' if n == 0 else f'  <-- {n} non-null value(s), superseded by container_id'
            print(f'   {table}.{col:<22} {n:>4} non-null{note}')

    # The one thing that must be true before dropping fridge_region_id.
    placed = conn.execute(
        'SELECT COUNT(*) c FROM drugs WHERE container_id IS NOT NULL'
    ).fetchone()['c']
    had_legacy = conn.execute(
        'SELECT COUNT(*) c FROM drugs WHERE fridge_region_id IS NOT NULL'
    ).fetchone()['c'] if 'fridge_region_id' in columns(conn, 'drugs') else 0
    print(f'\nSafety check: {placed} drug(s) located via container_id, '
          f'{had_legacy} via the legacy column.')
    if had_legacy > placed:
        print('   ! More legacy locations than container locations. '
              'Re-run migrate_containers.py --apply before cleaning up.')
        return False
    return True


def apply(conn, carries):
    cur = conn.cursor()

    # 1. Keep the photos.
    if 'photo' not in columns(conn, 'storage_containers'):
        cur.execute('ALTER TABLE storage_containers ADD COLUMN photo TEXT')
    carried = 0
    for c in carries:
        if c['container_id']:
            cur.execute('UPDATE storage_containers SET photo = ? WHERE id = ?',
                        (c['photo'], c['container_id']))
            carried += 1

    # 2. Drop the legacy columns. sqlite 3.35+ supports DROP COLUMN directly.
    dropped_cols = 0
    for table, cols in (('drugs', LEGACY_DRUG_COLUMNS),
                        ('primary_antibodies', LEGACY_ANTIBODY_COLUMNS),
                        ('secondary_antibodies', LEGACY_ANTIBODY_COLUMNS)):
        if not table_exists(conn, table):
            continue
        for col in cols:
            if col in columns(conn, table):
                cur.execute(f'ALTER TABLE "{table}" DROP COLUMN "{col}"')
                dropped_cols += 1

    # 3. Drop the legacy tables, children before parents.
    dropped_tables = 0
    for t in LEGACY_TABLES:
        if table_exists(conn, t):
            cur.execute(f'DROP TABLE "{t}"')
            dropped_tables += 1

    conn.commit()
    return {'photos_carried': carried, 'columns_dropped': dropped_cols,
            'tables_dropped': dropped_tables}


def verify(conn):
    problems = []
    for t in LEGACY_TABLES:
        if table_exists(conn, t):
            problems.append(f'{t} still present')
    for table, cols in (('drugs', LEGACY_DRUG_COLUMNS),
                        ('primary_antibodies', LEGACY_ANTIBODY_COLUMNS),
                        ('secondary_antibodies', LEGACY_ANTIBODY_COLUMNS)):
        if not table_exists(conn, table):
            continue
        for col in cols:
            if col in columns(conn, table):
                problems.append(f'{table}.{col} still present')

    # Locations must have survived the column surgery intact.
    n = conn.execute('SELECT COUNT(*) c FROM drugs WHERE container_id IS NOT NULL'
                     ).fetchone()['c']
    if n != 47:
        problems.append(f'{n} located drugs, expected 47')
    orphan = conn.execute(
        'SELECT COUNT(*) c FROM drugs WHERE container_id IS NOT NULL AND '
        'container_id NOT IN (SELECT id FROM storage_containers)').fetchone()['c']
    if orphan:
        problems.append(f'{orphan} drug(s) point at a missing container')
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='write the cleanup (default is a dry run)')
    args = ap.parse_args()

    if not DB.exists():
        raise SystemExit(f'No database at {DB}')

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    carries = plan_photo_carry(conn)
    safe = report(conn, carries)

    if not args.apply:
        print('\n--- DRY RUN: nothing written. Re-run with --apply to commit. ---')
        conn.close()
        return 0
    if not safe:
        print('\nRefusing to apply: the safety check above did not pass.')
        conn.close()
        return 1

    result = apply(conn, carries)
    problems = verify(conn)
    conn.close()

    print(f"\nCarried {result['photos_carried']} photo(s), dropped "
          f"{result['columns_dropped']} column(s) and "
          f"{result['tables_dropped']} table(s).")
    if problems:
        print('\nVERIFICATION FAILED')
        for p in problems:
            print(f'  x {p}')
        return 1
    print('Verification passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
