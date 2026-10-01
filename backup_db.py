"""Back up lab_management.db.

Writes three things into backups/:
  - a timestamped copy of the .db file (binary, gitignored)
  - schema.sql, the full CREATE statements
  - csv/<table>.csv, one file per table

The CSV and schema dumps are plain text, so committing them puts the *content*
of the database under version control even though *.db itself is gitignored.

Usage:  python backup_db.py
"""

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / 'lab_management.db'
BACKUPS = ROOT / 'backups'


def main():
    if not DB.exists():
        raise SystemExit(f'No database at {DB}')

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_dir = BACKUPS / 'csv'
    csv_dir.mkdir(parents=True, exist_ok=True)

    # Binary copy. Use the sqlite backup API rather than shutil so the copy is
    # consistent even if the Flask app happens to be running and mid-write.
    db_copy = BACKUPS / f'lab_management_{stamp}.db'
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dst = sqlite3.connect(db_copy)
    with dst:
        src.backup(dst)
    dst.close()
    print(f'db     -> {db_copy.relative_to(ROOT)}  ({db_copy.stat().st_size:,} bytes)')

    src.row_factory = sqlite3.Row
    cur = src.cursor()

    # Schema
    rows = cur.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
    ).fetchall()
    schema = (BACKUPS / 'schema.sql')
    schema.write_text(';\n\n'.join(r['sql'] for r in rows) + ';\n', encoding='utf-8')
    print(f'schema -> {schema.relative_to(ROOT)}  ({len(rows)} objects)')

    # One CSV per table
    tables = [
        r['name'] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table in tables:
        data = cur.execute(f'SELECT * FROM "{table}"').fetchall()
        path = csv_dir / f'{table}.csv'
        cols = [d[0] for d in cur.description]
        with path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(cols)
            writer.writerows([tuple(r) for r in data])
        print(f'csv    -> {path.relative_to(ROOT)}  ({len(data)} rows)')

    src.close()
    print(f'\nDone. {len(tables)} tables backed up at {stamp}.')


if __name__ == '__main__':
    main()
