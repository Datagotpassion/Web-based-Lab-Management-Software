"""Point-in-time history of every record, so a change can be undone.

The whole-database backups recover from losing the machine; they cannot put
back one record deleted last Tuesday without discarding everything entered
since. This keeps a snapshot of every row each time it changes, so a single
record can be restored, and so you can see what something looked like at any
point.

Implemented as SQLite triggers rather than calls in the application. Anything
that writes to the database is recorded -- a route added later, a CSV import,
the storage tree moving items between boxes, or someone running SQL by hand.
Hooks in Python would only cover the paths someone remembered to hook, and the
whole value of an audit trail is that it has no gaps.

Snapshots are written by the trigger with json_object(), so the stored row is
whatever the table actually held, with no separate list of columns to keep in
step.
"""

import json
import sqlite3
from datetime import datetime

# Tables worth keeping history for: the ones holding records people type in.
# The storage tree is deliberately excluded -- it changes constantly as items
# move, and its own structure is easy to rebuild.
TRACKED = ('drugs', 'primary_antibodies', 'secondary_antibodies')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS record_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    record_id   INTEGER NOT NULL,
    action      TEXT NOT NULL,          -- create | update | delete
    changed_at  TEXT NOT NULL,
    changed_by  TEXT,                   -- best effort; there is no login
    snapshot    TEXT NOT NULL           -- the row as JSON after the change,
                                        -- or as it last was, for a delete
);
CREATE INDEX IF NOT EXISTS idx_history_record
    ON record_history(table_name, record_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_history_time
    ON record_history(changed_at DESC);
'''


def _columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _json_object(columns, prefix):
    """json_object('col', NEW.col, ...) for a trigger body."""
    parts = ', '.join(f"'{c}', {prefix}.\"{c}\"" for c in columns)
    return f'json_object({parts})'


def ensure(conn):
    """Create the history table and (re)build the triggers.

    Triggers are dropped and recreated every time so that a column added to a
    tracked table is picked up; a stale trigger would quietly record an
    incomplete snapshot, which is worse than none.
    """
    conn.executescript(SCHEMA)
    for table in TRACKED:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        if not exists:
            continue
        cols = _columns(conn, table)
        if 'id' not in cols:
            continue

        for action, when, ref in (('create', 'INSERT', 'NEW'),
                                  ('update', 'UPDATE', 'NEW'),
                                  ('delete', 'DELETE', 'OLD')):
            name = f'{table}_history_{action}'
            conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
            conn.execute(f'''
                CREATE TRIGGER "{name}" AFTER {when} ON "{table}"
                BEGIN
                    INSERT INTO record_history
                        (table_name, record_id, action, changed_at, snapshot)
                    VALUES ('{table}', {ref}.id, '{action}',
                            datetime('now', 'localtime'),
                            {_json_object(cols, ref)});
                END
            ''')
    conn.commit()


def attribute(conn, actor, limit=12):
    """Mark the most recent unattributed entries with who made them.

    Triggers cannot know the caller, so the application names the actor just
    after writing. Best effort by nature, and meaningless until there is a
    login -- it records where a change came from, not who someone is.
    """
    if not actor:
        return
    conn.execute('''
        UPDATE record_history SET changed_by = ?
         WHERE changed_by IS NULL
           AND id > (SELECT COALESCE(MAX(id), 0) - ? FROM record_history)
    ''', (actor, limit))


def recent(conn, limit=100, table=None):
    """Most recent changes across all tracked tables."""
    sql = ('SELECT id, table_name, record_id, action, changed_at, changed_by,'
           ' snapshot FROM record_history')
    params = []
    if table:
        sql += ' WHERE table_name = ?'
        params.append(table)
    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)
    return [_row(r) for r in conn.execute(sql, params)]


def for_record(conn, table, record_id):
    """Every version of one record, newest first."""
    return [_row(r) for r in conn.execute(
        'SELECT id, table_name, record_id, action, changed_at, changed_by,'
        ' snapshot FROM record_history WHERE table_name = ? AND record_id = ?'
        ' ORDER BY id DESC', (table, record_id))]


def deleted(conn, table=None):
    """Records whose most recent entry is a deletion -- the restorable ones."""
    sql = '''
        SELECT h.id, h.table_name, h.record_id, h.action, h.changed_at,
               h.changed_by, h.snapshot
          FROM record_history h
          JOIN (SELECT table_name, record_id, MAX(id) AS last
                  FROM record_history GROUP BY table_name, record_id) m
            ON m.table_name = h.table_name AND m.record_id = h.record_id
           AND m.last = h.id
         WHERE h.action = 'delete'
    '''
    params = []
    if table:
        sql += ' AND h.table_name = ?'
        params.append(table)
    return [_row(r) for r in conn.execute(sql + ' ORDER BY h.id DESC', params)]


def restore(conn, history_id):
    """Put a record back as it was at that point.

    Re-inserts with the original id when nothing occupies it, so references
    elsewhere -- a container holding the item, say -- still resolve. If the id
    has since been taken, a new one is assigned rather than overwriting
    somebody else's record.
    """
    row = conn.execute(
        'SELECT table_name, record_id, snapshot FROM record_history WHERE id = ?',
        (history_id,)).fetchone()
    if row is None:
        raise ValueError(f'No history entry {history_id}')

    table, record_id, data = row[0], row[1], json.loads(row[2])
    if table not in TRACKED:
        raise ValueError(f'{table} is not a tracked table')

    live = _columns(conn, table)
    # A column dropped since the snapshot is skipped rather than failing the
    # restore; one added since simply takes its default.
    fields = [c for c in data if c in live]

    taken = conn.execute(f'SELECT 1 FROM "{table}" WHERE id = ?',
                         (record_id,)).fetchone()
    if taken:
        fields = [c for c in fields if c != 'id']

    placeholders = ', '.join('?' * len(fields))
    cols = ', '.join(f'"{c}"' for c in fields)
    cur = conn.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})',
                       [data[c] for c in fields])
    conn.commit()
    return {'table': table, 'id': cur.lastrowid,
            'reused_original_id': not taken}


def _row(r):
    return {'history_id': r[0], 'table': r[1], 'record_id': r[2],
            'action': r[3], 'changed_at': r[4], 'changed_by': r[5],
            'snapshot': json.loads(r[6])}


def describe(entry, previous=None):
    """Which fields changed, for showing a history entry in one line."""
    if entry['action'] == 'create':
        return 'created'
    if entry['action'] == 'delete':
        return 'deleted'
    if not previous:
        return 'updated'
    now, before = entry['snapshot'], previous['snapshot']
    changed = [k for k in now
               if k not in ('id',) and now.get(k) != before.get(k)]
    return 'changed ' + ', '.join(changed[:6]) if changed else 'saved, no change'
