"""Migrate the flat schematic-zone model to a nested storage container tree.

Why
---
Locations are currently spread over four tables (fridge_config, fridge_layouts,
fridge_regions, fridge_schematic_layouts, fridge_schematic_zones), only one of
which is live, and the live one is a flat 2D grid of name strings. That means:

  * "Shelf 2B" is one opaque label, so the app cannot tell shelf 2 from rack B
    and cannot answer "which racks are on shelf 2" or "which boxes are in rack B";
  * there is no level below the rack, so items pile into one bucket;
  * temperature and owning lab are encoded in zone names ("Shelf 3 4C Amy Lab")
    because the schema has nowhere to put them.

This migration introduces storage_units + a self-referencing storage_containers
table, so the -80 C freezer can nest section > shelf > rack > box while the
4 C fridge stays one level deep, with no special-casing.

Safety
------
Nothing is dropped or rewritten. The legacy tables are left exactly as they are
and the existing drugs.fridge_region_id column is preserved, so app.py keeps
working unchanged after this runs. A separate cleanup can drop the dead tables
once the UI is ported. Re-running is safe: --apply rebuilds the tree from
scratch each time, remapping items from the legacy columns.

Usage
-----
    python migrate_containers.py            # dry run, prints the planned tree
    python migrate_containers.py --apply    # write it
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# The container schema lives in storage.py so there is a single definition.
from storage import DDL

DB = Path(__file__).parent / 'lab_management.db'

# A zone name is a "rack cell" when it is letters/spaces, then a number, then a
# single trailing capital: "Shelf 1A" -> (Shelf, 1, A). The base is restricted
# to [A-Za-z ] on purpose, so "Shelf 2 -20C" cannot be mis-read as rack "C" of
# shelf 20 -- that string contains digits and a hyphen in the base position.
RACK_CELL = re.compile(r'^(?P<base>[A-Za-z ]+?)\s*(?P<num>\d+)\s*(?P<letter>[A-Z])$')

# Owning-lab and temperature tokens that are currently baked into zone names.
LAB_TOKEN = re.compile(r'\b(\w+ Lab)\b')
TEMP_TOKEN = re.compile(r'(?:(?<=\s)|^)(-?\d{1,3})\s*C\b')

UNIT_KINDS = {'-80C': 'ultralow', '-20C': 'freezer', '4C': 'fridge'}


def temp_from_key(temp_key):
    """'-80C' -> -80.0"""
    m = re.match(r'^(-?\d+)C$', (temp_key or '').strip())
    return float(m.group(1)) if m else None


def infer_kind(label):
    low = label.lower()
    if 'drawer' in low:
        return 'drawer'
    if 'bin' in low:
        return 'bin'
    return 'shelf'


def parse_zone_name(name):
    """Pull owner lab and temperature out of a zone name.

    Returns (label, temp_c, owner_lab, warning).
    """
    label, owner_lab, temp_c = name.strip(), None, None

    m = LAB_TOKEN.search(label)
    if m:
        owner_lab = m.group(1)
        label = label[:m.start()] + label[m.end():]

    m = TEMP_TOKEN.search(label)
    if m:
        temp_c = float(m.group(1))
        label = label[:m.start()] + label[m.end():]

    label = re.sub(r'\s+', ' ', label).strip(' -')

    warning = None
    # "Shelf -20C" cleans down to a bare noun with no identifying number.
    if len(label) < 3 or not re.search(r'\d', label):
        warning = f'ambiguous label {label!r} from zone {name!r} - worth renaming'
        if len(label) < 3:
            label = name.strip()

    return label, temp_c, owner_lab, warning


def classify_layout(zone_names):
    """Is this layout a shelf x rack grid, or a flat list of named zones?"""
    cells = [RACK_CELL.match(n.strip()) for n in zone_names]
    if not zone_names or not all(cells):
        return 'flat'
    letters = {c.group('letter') for c in cells}
    numbers = {c.group('num') for c in cells}
    # A real rack grid has several racks across several shelves. One of each is
    # just a coincidentally-named single zone.
    return 'rack_grid' if len(letters) > 1 and len(numbers) > 1 else 'flat'


class Node:
    """A planned container, held in memory so --dry-run can print the tree."""

    def __init__(self, unit_id, kind, label, *, parent=None, temp_c=None,
                 owner_lab=None, pos_row=0, pos_col=0, row_span=1, col_span=1,
                 color=None, legacy_zone_id=None):
        self.unit_id = unit_id
        self.kind = kind
        self.label = label
        self.parent = parent
        self.temp_c = temp_c
        self.owner_lab = owner_lab
        self.pos_row = pos_row
        self.pos_col = pos_col
        self.row_span = row_span
        self.col_span = col_span
        self.color = color
        self.legacy_zone_id = legacy_zone_id
        self.children = []
        self.db_id = None
        if parent is not None:
            parent.children.append(self)


def build_plan(conn):
    """Read the legacy tables and plan the new tree. Pure: writes nothing."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    units = [dict(r) for r in cur.execute('SELECT * FROM fridges ORDER BY id')]
    layouts = [dict(r) for r in cur.execute(
        'SELECT * FROM fridge_schematic_layouts ORDER BY fridge_id, section, id')]
    zones_by_layout = {}
    for r in cur.execute('SELECT * FROM fridge_schematic_zones '
                         'ORDER BY layout_id, row_index, col_index'):
        zones_by_layout.setdefault(r['layout_id'], []).append(dict(r))

    roots, warnings = [], []
    # legacy zone id -> planned Node that items pointing at it should move to
    zone_to_node = {}

    for unit in units:
        unit_layouts = [l for l in layouts if l['fridge_id'] == unit['id']]
        if not unit_layouts:
            warnings.append(f"unit {unit['name']!r} has no layout - no containers created")

        for layout in unit_layouts:
            section_label = (layout['section'] or 'body').capitalize()
            section = Node(unit['id'], 'section', section_label)
            roots.append(section)

            zones = zones_by_layout.get(layout['id'], [])
            if not zones:
                continue

            mode = classify_layout([z['zone_name'] for z in zones])

            if mode == 'rack_grid':
                # Split "Shelf 2B" into shelf "Shelf 2" + rack "B".
                shelves = {}
                for z in zones:
                    m = RACK_CELL.match(z['zone_name'].strip())
                    base, num, letter = (m.group('base').strip(),
                                         m.group('num'), m.group('letter'))
                    shelf_label = f'{base} {num}'.strip()
                    if shelf_label not in shelves:
                        shelves[shelf_label] = Node(
                            unit['id'], 'shelf', shelf_label, parent=section,
                            pos_row=z['row_index'], pos_col=0)
                    rack = Node(unit['id'], 'rack', letter,
                                parent=shelves[shelf_label],
                                pos_row=0, pos_col=z['col_index'],
                                color=z['color'], legacy_zone_id=z['id'])
                    zone_to_node[z['id']] = rack
            else:
                for z in zones:
                    label, temp_c, owner_lab, warn = parse_zone_name(z['zone_name'])
                    if warn:
                        warnings.append(f"{unit['name']} / {section_label}: {warn}")
                    node = Node(unit['id'], infer_kind(label), label,
                                parent=section, temp_c=temp_c, owner_lab=owner_lab,
                                pos_row=z['row_index'], pos_col=z['col_index'],
                                row_span=z['row_span'], col_span=z['col_span'],
                                color=z['color'], legacy_zone_id=z['id'])
                    zone_to_node[z['id']] = node

    return units, roots, zone_to_node, warnings


def item_mapping(conn, zone_to_node):
    """Which items land where, and which point at a zone that no longer exists."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    mapped, orphaned = [], []
    tables = [('drugs', 'drug_name'),
              ('primary_antibodies', 'name'),
              ('secondary_antibodies', 'name')]
    for table, name_col in tables:
        cols = [c[1] for c in cur.execute(f'PRAGMA table_info({table})')]
        if 'fridge_region_id' not in cols:
            continue
        rows = cur.execute(
            f'SELECT id, "{name_col}" AS nm, fridge_region_id FROM {table} '
            'WHERE fridge_region_id IS NOT NULL').fetchall()
        for r in rows:
            node = zone_to_node.get(r['fridge_region_id'])
            if node is None:
                orphaned.append((table, r['id'], r['nm'], r['fridge_region_id']))
            else:
                mapped.append((table, r['id'], r['nm'], node))
    return mapped, orphaned


def path_of(node, unit_by_id=None):
    """Full human-readable address, e.g. '-80°C Freezer > Body > Shelf 2 > Rack B'."""
    parts, cur = [], node
    while cur is not None:
        # A bare rack label is just "B"; spell out the kind so the path reads.
        parts.append(f'Rack {cur.label}' if cur.kind == 'rack' else cur.label)
        cur = cur.parent
    if unit_by_id is not None:
        parts.append(unit_by_id[node.unit_id]['name'])
    return ' > '.join(reversed(parts))


def print_plan(units, roots, mapped, orphaned, warnings):
    unit_by_id = {u['id']: u for u in units}
    counts = {}
    for _, _, _, node in mapped:
        counts[id(node)] = counts.get(id(node), 0) + 1

    print('=' * 72)
    print('PLANNED STORAGE TREE')
    print('=' * 72)

    current_unit = None
    for root in roots:
        unit = unit_by_id[root.unit_id]
        if unit['id'] != current_unit:
            current_unit = unit['id']
            temp = temp_from_key(unit['temp_type'])
            print(f"\n{unit['name']}  [{UNIT_KINDS.get(unit['temp_type'], 'fridge')}"
                  f"{f', {temp:g} °C' if temp is not None else ''}"
                  f"{f', {unit['location']}' if unit['location'] else ''}]")

        def walk(node, depth=1):
            pad = '    ' * depth
            bits = [f'({node.kind})']
            if node.temp_c is not None:
                bits.append(f'{node.temp_c:g} °C')
            if node.owner_lab:
                bits.append(node.owner_lab)
            n = counts.get(id(node), 0)
            if n:
                bits.append(f'** {n} item{"s" if n != 1 else ""} **')
            print(f'{pad}{node.label:<28} {" ".join(bits)}')
            for child in node.children:
                walk(child, depth + 1)

        walk(root)

    total_containers = sum(_count(r) for r in roots)
    print('\n' + '=' * 72)
    print(f'{len(units)} units, {total_containers} containers, {len(mapped)} items placed')

    if warnings:
        print('\nWARNINGS')
        for w in warnings:
            print(f'  ! {w}')

    if orphaned:
        print('\nORPHANED ITEMS (legacy zone id no longer exists; will be left unplaced)')
        for table, pk, nm, zid in orphaned:
            print(f'  ? {table}#{pk} {nm!r} -> zone {zid}')

    print('\nITEM PLACEMENT')
    by_node = {}
    for table, pk, nm, node in mapped:
        by_node.setdefault(id(node), (node, []))[1].append(nm)
    for node, names in sorted(by_node.values(), key=lambda x: -len(x[1])):
        print(f'  {path_of(node, unit_by_id)}  ({len(names)})')
        for nm in sorted(names)[:4]:
            print(f'      - {nm}')
        if len(names) > 4:
            print(f'      ... and {len(names) - 4} more')


def _count(node):
    return 1 + sum(_count(c) for c in node.children)


def apply_plan(conn, units, roots, mapped):
    cur = conn.cursor()
    cur.executescript(DDL)

    # container_id on each item table, alongside the legacy column.
    for table in ('drugs', 'primary_antibodies', 'secondary_antibodies'):
        cols = [c[1] for c in cur.execute(f'PRAGMA table_info({table})')]
        if 'container_id' not in cols:
            cur.execute(f'ALTER TABLE {table} ADD COLUMN container_id INTEGER')

    # Rebuild from scratch so re-running is idempotent.
    cur.execute('DELETE FROM storage_containers')
    cur.execute('DELETE FROM storage_units')

    for u in units:
        # No has_door flag: whether a unit has door storage is simply whether a
        # "Door" section container exists under it. A unit can have none, one,
        # or several, at whatever temperatures they actually run.
        cur.execute(
            'INSERT INTO storage_units (id, name, kind, room, default_temp_c) '
            'VALUES (?, ?, ?, ?, ?)',
            (u['id'], u['name'], UNIT_KINDS.get(u['temp_type'], 'fridge'),
             u['location'], temp_from_key(u['temp_type'])))

    def insert(node, parent_id):
        cur.execute(
            'INSERT INTO storage_containers (unit_id, parent_id, kind, label, temp_c,'
            ' owner_lab, pos_row, pos_col, row_span, col_span, color, legacy_zone_id)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (node.unit_id, parent_id, node.kind, node.label, node.temp_c,
             node.owner_lab, node.pos_row, node.pos_col, node.row_span,
             node.col_span, node.color, node.legacy_zone_id))
        node.db_id = cur.lastrowid
        for child in node.children:
            insert(child, node.db_id)

    for root in roots:
        insert(root, None)

    for table, pk, _nm, node in mapped:
        cur.execute(f'UPDATE {table} SET container_id = ? WHERE id = ?',
                    (node.db_id, pk))

    conn.commit()


def verify(conn, mapped):
    """Post-apply sanity checks. Returns a list of failure strings."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    problems = []

    n_units = cur.execute('SELECT COUNT(*) c FROM storage_units').fetchone()['c']
    n_legacy_units = cur.execute('SELECT COUNT(*) c FROM fridges').fetchone()['c']
    if n_units != n_legacy_units:
        problems.append(f'unit count {n_units} != legacy {n_legacy_units}')

    # Every item that had a legacy location must now have a container.
    for table in ('drugs', 'primary_antibodies', 'secondary_antibodies'):
        expected = cur.execute(
            f'SELECT COUNT(*) c FROM {table} WHERE fridge_region_id IN '
            '(SELECT legacy_zone_id FROM storage_containers '
            ' WHERE legacy_zone_id IS NOT NULL)').fetchone()['c']
        actual = cur.execute(
            f'SELECT COUNT(*) c FROM {table} WHERE container_id IS NOT NULL'
        ).fetchone()['c']
        if expected != actual:
            problems.append(f'{table}: {actual} placed, expected {expected}')

    # No container may point outside the tree or at itself.
    bad = cur.execute(
        'SELECT COUNT(*) c FROM storage_containers c1 WHERE parent_id IS NOT NULL '
        'AND (parent_id = c1.id OR parent_id NOT IN '
        '(SELECT id FROM storage_containers))').fetchone()['c']
    if bad:
        problems.append(f'{bad} containers with a broken parent_id')

    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true',
                    help='write the migration (default is a dry run)')
    args = ap.parse_args()

    if not DB.exists():
        raise SystemExit(f'No database at {DB}')

    conn = sqlite3.connect(DB)
    units, roots, zone_to_node, warnings = build_plan(conn)
    mapped, orphaned = item_mapping(conn, zone_to_node)
    print_plan(units, roots, mapped, orphaned, warnings)

    if not args.apply:
        print('\n--- DRY RUN: nothing written. Re-run with --apply to commit. ---')
        conn.close()
        return 0

    apply_plan(conn, units, roots, mapped)
    problems = verify(conn, mapped)
    conn.close()

    if problems:
        print('\nVERIFICATION FAILED')
        for p in problems:
            print(f'  x {p}')
        return 1
    print('\nApplied. Verification passed. Legacy tables and columns untouched.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
