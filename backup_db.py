"""Back up lab_management.db.

Writes three things into backups/:
  - a timestamped copy of the .db file (binary, gitignored)
  - schema.sql, the full CREATE statements
  - csv/<table>.csv, one file per table

The CSV and schema dumps are plain text, so committing them puts the *content*
of the database under version control even though *.db itself is gitignored.

Usage:  python backup_db.py
"""

import argparse
import csv
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / 'lab_management.db'
BACKUPS = ROOT / 'backups'

# Enough history to recover from a mistake noticed weeks later, while keeping
# the directory manageable. At ~90 KB a copy this is trivial on disk.
KEEP = 30


def default_destinations():
    """Where copies go, in increasing order of what they survive.

    A backup inside the project directory does not survive losing that
    directory, and one on this machine does not survive losing the machine --
    so copies are written to somewhere off the project tree and into a
    cloud-synced folder, where the sync client does the upload. That needs no
    API credentials and works the same for OneDrive or Google Drive.

    Override entirely with LABMANAGER_BACKUP_DIRS (os.pathsep separated).
    """
    override = os.environ.get('LABMANAGER_BACKUP_DIRS', '').strip()
    if override:
        return [BACKUPS] + [Path(p) for p in override.split(os.pathsep) if p.strip()]

    targets = [BACKUPS]

    # Off the project tree, so deleting the project does not take the backups.
    sibling = ROOT.parent / 'LabManagementBackups'
    targets.append(sibling)

    # Off the machine, via whichever sync client is installed.
    for var in ('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer'):
        root = os.environ.get(var)
        if root and Path(root).is_dir():
            targets.append(Path(root) / 'LabManagement Backups')
            break
    else:
        for candidate in (Path.home() / 'Google Drive',
                          Path.home() / 'My Drive',
                          Path.home() / 'Dropbox'):
            if candidate.is_dir():
                targets.append(candidate / 'LabManagement Backups')
                break

    # De-duplicate while keeping order.
    seen, unique = set(), []
    for t in targets:
        key = str(t).lower()
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def prune(where, keep=KEEP):
    """Drop the oldest binary copies in one destination, keeping `keep`.

    Only the .db files are pruned. schema.sql and the CSVs are overwritten in
    place each run and are versioned in git, which is the real history.
    """
    copies = sorted(Path(where).glob('lab_management_*.db'),
                    key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for old in copies[keep:]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed, len(copies) - removed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--quiet', action='store_true',
                    help='only report problems (for scheduled runs)')
    ap.add_argument('--keep', type=int, default=KEEP,
                    help=f'how many binary copies to retain (default {KEEP})')
    ap.add_argument('--to', action='append', metavar='DIR',
                    help='destination directory; repeatable. Overrides the '
                         'defaults (project, off-tree, cloud-synced folder)')
    args = ap.parse_args()

    def say(msg):
        if not args.quiet:
            print(msg)

    if not DB.exists():
        raise SystemExit(f'No database at {DB}')

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    destinations = ([Path(p) for p in args.to] if args.to
                    else default_destinations())

    # Build the copy once, into the project's own backups directory.
    BACKUPS.mkdir(parents=True, exist_ok=True)
    (BACKUPS / 'csv').mkdir(parents=True, exist_ok=True)

    # Binary copy. Use the sqlite backup API rather than shutil so the copy is
    # consistent even if the Flask app happens to be running and mid-write.
    db_copy = BACKUPS / f'lab_management_{stamp}.db'
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dst = sqlite3.connect(db_copy)
    with dst:
        src.backup(dst)
    dst.close()

    src.row_factory = sqlite3.Row
    cur = src.cursor()

    rows = cur.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    ).fetchall()
    (BACKUPS / 'schema.sql').write_text(
        ';\n\n'.join(r['sql'] for r in rows) + ';\n', encoding='utf-8')

    tables = [
        r['name'] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table in tables:
        data = cur.execute(f'SELECT * FROM "{table}"').fetchall()
        cols = [d[0] for d in cur.description]
        with (BACKUPS / 'csv' / f'{table}.csv').open(
                'w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(cols)
            writer.writerows([tuple(r) for r in data])
    src.close()
    say(f'built  -> {len(tables)} tables, {db_copy.stat().st_size:,} bytes')

    # Copy to every destination. One unreachable target -- a disconnected
    # drive, a paused sync client -- must not stop the others, so each is
    # reported separately and failures do not abort the run.
    failures = 0
    for dest in destinations:
        try:
            if dest != BACKUPS:
                (dest / 'csv').mkdir(parents=True, exist_ok=True)
                shutil.copy2(db_copy, dest / db_copy.name)
                shutil.copy2(BACKUPS / 'schema.sql', dest / 'schema.sql')
                for table in tables:
                    shutil.copy2(BACKUPS / 'csv' / f'{table}.csv',
                                 dest / 'csv' / f'{table}.csv')
            removed, kept = prune(dest, args.keep)
            say(f'  ok   {dest}  ({kept} copies, pruned {removed})')
        except OSError as exc:
            failures += 1
            # Printed even when quiet: a destination silently not receiving
            # backups is the whole failure mode this exists to prevent.
            print(f'  FAILED {dest}: {exc}', file=sys.stderr)

    say(f'\nDone at {stamp}; {len(destinations) - failures} of '
        f'{len(destinations)} destinations written.')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
