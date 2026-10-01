"""Storage container tree: units, nested containers, and the items inside them.

The tree is deliberately unconstrained in shape. Nothing here requires a unit to
have a door, requires shelves to hold the same number of racks, or fixes how deep
the nesting goes. A unit's structure is whatever containers exist under it, and a
row's width is derived from its actual children rather than declared anywhere.
That is the whole point: the physical freezer is irregular, so the model has to be.

Deletion is done with explicit recursive SQL rather than ON DELETE CASCADE,
because sqlite only honours foreign keys when PRAGMA foreign_keys is ON per
connection and the rest of this codebase never sets it. Relying on the pragma
would make cascade behaviour depend on which module opened the connection.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / 'lab_management.db'

# Tables whose rows can live in a container, with the column holding their name.
ITEM_TABLES = (
    ('drugs', 'drug_name'),
    ('primary_antibodies', 'name'),
    ('secondary_antibodies', 'name'),
)

# Open vocabulary. Not enforced as a constraint -- it drives the UI's pick list
# and the default child axis, but an unlisted kind is stored happily.
KINDS = ('section', 'shelf', 'rack', 'drawer', 'bin', 'box', 'tray', 'other')

UNIT_KINDS = ('fridge', 'freezer', 'ultralow', 'ln2', 'incubator', 'cabinet', 'other')

# Racks sit side by side along a shelf; most other things stack downwards.
DEFAULT_AXIS = {'rack': 'col'}


class StorageError(Exception):
    """A rejected operation, with a message meant for the user."""


# Canonical schema for the container tree. migrate_containers imports this so
# there is one definition, and ensure_schema() runs it on startup so a fresh
# install (a new Pi, a test database) comes up with the tables present.
DDL = '''
CREATE TABLE IF NOT EXISTS storage_units (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'fridge',
    room            TEXT,
    default_temp_c  REAL,
    notes           TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS storage_containers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id     INTEGER NOT NULL,
    parent_id   INTEGER,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    temp_c      REAL,
    owner_lab   TEXT,
    grid_rows   INTEGER,
    grid_cols   INTEGER,
    pos_row     INTEGER DEFAULT 0,
    pos_col     INTEGER DEFAULT 0,
    row_span    INTEGER DEFAULT 1,
    col_span    INTEGER DEFAULT 1,
    depth_index INTEGER DEFAULT 0,
    color       TEXT,
    legacy_zone_id INTEGER,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id)   REFERENCES storage_units(id)      ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES storage_containers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_containers_parent ON storage_containers(parent_id);
CREATE INDEX IF NOT EXISTS idx_containers_unit   ON storage_containers(unit_id);
CREATE INDEX IF NOT EXISTS idx_containers_legacy ON storage_containers(legacy_zone_id);
'''


class StorageTree:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = str(db_path)

    @contextmanager
    def _conn(self):
        """Commit on success, roll back on error, and always close.

        `with sqlite3.connect(...)` commits but never closes, which leaks file
        handles in a long-running server, so the close lives here instead.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Defence in depth; the explicit deletes below do not depend on it.
        conn.execute('PRAGMA foreign_keys = ON')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_schema(self):
        """Create the container tables and the item container_id columns.

        Idempotent, and safe to call on every startup. Without this a fresh
        database (new install, or a test fixture) has no storage tables and
        no container_id to write locations into.
        """
        with self._conn() as c:
            c.executescript(DDL)
            for table, _ in ITEM_TABLES:
                exists = c.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)).fetchone()
                if not exists:
                    continue
                cols = [r[1] for r in c.execute(f'PRAGMA table_info({table})')]
                if 'container_id' not in cols:
                    c.execute(f'ALTER TABLE {table} ADD COLUMN container_id INTEGER')
        return self

    # ---------------------------------------------------------------- units

    def list_units(self):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                'SELECT * FROM storage_units ORDER BY name')]

    def get_unit(self, unit_id):
        with self._conn() as c:
            row = c.execute('SELECT * FROM storage_units WHERE id = ?',
                            (unit_id,)).fetchone()
        if row is None:
            raise StorageError(f'No storage unit with id {unit_id}')
        return dict(row)

    def create_unit(self, name, kind='fridge', room=None,
                    default_temp_c=None, notes=None):
        name = (name or '').strip()
        if not name:
            raise StorageError('A unit needs a name')
        with self._conn() as c:
            cur = c.execute(
                'INSERT INTO storage_units (name, kind, room, default_temp_c, notes)'
                ' VALUES (?,?,?,?,?)',
                (name, kind, room or None, _num(default_temp_c), notes or None))
            new_id = cur.lastrowid
        # Read back only after the transaction has committed.
        return self.get_unit(new_id)

    def update_unit(self, unit_id, **fields):
        self.get_unit(unit_id)  # existence check
        allowed = ('name', 'kind', 'room', 'default_temp_c', 'notes')
        sets, params = [], []
        for key in allowed:
            if key in fields:
                value = fields[key]
                if key == 'name':
                    value = (value or '').strip()
                    if not value:
                        raise StorageError('A unit needs a name')
                elif key == 'default_temp_c':
                    value = _num(value)
                else:
                    value = value or None
                sets.append(f'{key} = ?')
                params.append(value)
        if sets:
            params.append(unit_id)
            with self._conn() as c:
                c.execute(f'UPDATE storage_units SET {", ".join(sets)} WHERE id = ?',
                          params)
        return self.get_unit(unit_id)

    def delete_unit(self, unit_id):
        """Remove a unit and everything in it. Items inside become unplaced."""
        self.get_unit(unit_id)
        with self._conn() as c:
            ids = [r['id'] for r in c.execute(
                'SELECT id FROM storage_containers WHERE unit_id = ?', (unit_id,))]
            unplaced = self._unplace_items(c, ids)
            c.execute('DELETE FROM storage_containers WHERE unit_id = ?', (unit_id,))
            c.execute('DELETE FROM storage_units WHERE id = ?', (unit_id,))
        return {'removed_containers': len(ids), 'unplaced_items': unplaced}

    # ----------------------------------------------------------- containers

    def get_container(self, container_id):
        with self._conn() as c:
            row = c.execute('SELECT * FROM storage_containers WHERE id = ?',
                            (container_id,)).fetchone()
        if row is None:
            raise StorageError(f'No container with id {container_id}')
        return dict(row)

    def create_container(self, unit_id, parent_id=None, kind='shelf', label='',
                         temp_c=None, owner_lab=None, pos_row=None, pos_col=None,
                         grid_rows=None, grid_cols=None, notes=None):
        label = (label or '').strip()
        if not label:
            raise StorageError('A container needs a label')
        self.get_unit(unit_id)

        if parent_id is not None:
            parent = self.get_container(parent_id)
            if parent['unit_id'] != unit_id:
                raise StorageError('Parent belongs to a different storage unit')

        axis = DEFAULT_AXIS.get(kind, 'row')
        if pos_row is None or pos_col is None:
            nxt = self._next_position(parent_id, unit_id, axis)
            pos_row = nxt[0] if pos_row is None else pos_row
            pos_col = nxt[1] if pos_col is None else pos_col

        with self._conn() as c:
            cur = c.execute(
                'INSERT INTO storage_containers (unit_id, parent_id, kind, label,'
                ' temp_c, owner_lab, pos_row, pos_col, grid_rows, grid_cols)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (unit_id, parent_id, kind, label, _num(temp_c),
                 owner_lab or None, pos_row, pos_col,
                 int(grid_rows) if grid_rows else None,
                 int(grid_cols) if grid_cols else None))
            new_id = cur.lastrowid
        return self.get_container(new_id)

    def bulk_create_children(self, parent_id, kind, count, scheme='letters',
                             prefix='', start=1):
        """Add `count` children at once -- the thing that makes a 5-shelf,
        4-rack freezer bearable to set up. Returns the created containers."""
        if count < 1 or count > 100:
            raise StorageError('Count must be between 1 and 100')
        parent = self.get_container(parent_id)
        axis = DEFAULT_AXIS.get(kind, 'row')
        base_row, base_col = self._next_position(parent_id, parent['unit_id'], axis)

        created = []
        with self._conn() as c:
            for i in range(count):
                label = f'{prefix}{_label_for(i + start - 1, scheme)}'
                row = base_row + (i if axis == 'row' else 0)
                col = base_col + (i if axis == 'col' else 0)
                cur = c.execute(
                    'INSERT INTO storage_containers (unit_id, parent_id, kind,'
                    ' label, pos_row, pos_col) VALUES (?,?,?,?,?,?)',
                    (parent['unit_id'], parent_id, kind, label, row, col))
                created.append(cur.lastrowid)
        return [self.get_container(i) for i in created]

    def update_container(self, container_id, **fields):
        self.get_container(container_id)
        allowed = ('kind', 'label', 'temp_c', 'owner_lab', 'pos_row', 'pos_col',
                   'row_span', 'col_span', 'depth_index', 'color',
                   # How this container's children are physically arranged --
                   # a rack holding boxes in a 4-wide, 3-tall matrix is
                   # grid_cols=4, grid_rows=3. Drives the spatial view.
                   'grid_rows', 'grid_cols')
        sets, params = [], []
        for key in allowed:
            if key in fields:
                value = fields[key]
                if key == 'label':
                    value = (value or '').strip()
                    if not value:
                        raise StorageError('A container needs a label')
                elif key == 'temp_c':
                    value = _num(value)
                elif key in ('pos_row', 'pos_col', 'row_span', 'col_span',
                             'depth_index'):
                    value = int(value or 0)
                elif key in ('grid_rows', 'grid_cols'):
                    # NULL means "no declared shape"; 0 would claim an empty
                    # grid, which is a different and wrong thing.
                    value = int(value) if value not in (None, '') else None
                    if value is not None and not 1 <= value <= 50:
                        raise StorageError(
                            f'{key} must be between 1 and 50, got {value}')
                else:
                    value = value or None
                sets.append(f'{key} = ?')
                params.append(value)
        if sets:
            params.append(container_id)
            with self._conn() as c:
                c.execute(f'UPDATE storage_containers SET {", ".join(sets)} '
                          'WHERE id = ?', params)
        return self.get_container(container_id)

    def delete_container(self, container_id, force=False):
        """Delete a container and its subtree.

        Items in the subtree are moved up to the deleted container's parent
        rather than being dropped, so nothing silently loses its location. If
        the subtree holds items and force is False, the delete is refused and
        the caller is told how many would move.
        """
        node = self.get_container(container_id)
        with self._conn() as c:
            subtree = self._subtree_ids(c, container_id)
            n_items = self._count_items(c, subtree)
            if n_items and not force:
                raise StorageError(
                    f'{node["label"]!r} and what is inside it hold {n_items} '
                    f'item(s). Deleting will move them up to the parent.')
            moved = self._move_items(c, subtree, node['parent_id'])
            c.executemany('DELETE FROM storage_containers WHERE id = ?',
                          [(i,) for i in subtree])
        return {'removed_containers': len(subtree), 'moved_items': moved,
                'moved_to': node['parent_id']}

    def move_container(self, container_id, new_parent_id=None,
                       pos_row=None, pos_col=None):
        """Reparent and/or reposition. Refuses to create a cycle."""
        node = self.get_container(container_id)

        if new_parent_id is not None:
            if int(new_parent_id) == int(container_id):
                raise StorageError('A container cannot be its own parent')
            parent = self.get_container(new_parent_id)
            with self._conn() as c:
                if int(new_parent_id) in self._subtree_ids(c, container_id):
                    raise StorageError(
                        f'Cannot move {node["label"]!r} into its own descendant '
                        f'{parent["label"]!r}')
            target_unit = parent['unit_id']
        else:
            target_unit = node['unit_id']

        if pos_row is None and pos_col is None:
            axis = DEFAULT_AXIS.get(node['kind'], 'row')
            pos_row, pos_col = self._next_position(new_parent_id, target_unit, axis)

        with self._conn() as c:
            subtree = self._subtree_ids(c, container_id)
            c.execute('UPDATE storage_containers SET parent_id = ?, pos_row = ?,'
                      ' pos_col = ? WHERE id = ?',
                      (new_parent_id, int(pos_row or 0), int(pos_col or 0),
                       container_id))
            # A cross-unit move takes the whole subtree with it.
            if target_unit != node['unit_id']:
                c.executemany('UPDATE storage_containers SET unit_id = ? WHERE id = ?',
                              [(target_unit, i) for i in subtree])
        return self.get_container(container_id)

    def reorder(self, container_id, direction):
        """Swap a container with its neighbour among its siblings."""
        if direction not in ('up', 'down'):
            raise StorageError("direction must be 'up' or 'down'")
        node = self.get_container(container_id)
        axis = DEFAULT_AXIS.get(node['kind'], 'row')
        field = 'pos_col' if axis == 'col' else 'pos_row'

        with self._conn() as c:
            siblings = [dict(r) for r in c.execute(
                f'SELECT * FROM storage_containers WHERE parent_id IS ?'
                f' ORDER BY {field}, id', (node['parent_id'],))]
            idx = next(i for i, s in enumerate(siblings) if s['id'] == node['id'])
            swap = idx - 1 if direction == 'up' else idx + 1
            # Already at the end of its row; nothing to swap with.
            if 0 <= swap < len(siblings):
                other = siblings[swap]
                c.execute(f'UPDATE storage_containers SET {field} = ? WHERE id = ?',
                          (other[field], node['id']))
                c.execute(f'UPDATE storage_containers SET {field} = ? WHERE id = ?',
                          (node[field], other['id']))
        return self.get_container(container_id)

    # ---------------------------------------------------------------- reads

    def get_tree(self, unit_id=None):
        """Units with their containers nested, each carrying item counts."""
        units = self.list_units() if unit_id is None else [self.get_unit(unit_id)]
        with self._conn() as c:
            params = () if unit_id is None else (unit_id,)
            where = '' if unit_id is None else 'WHERE unit_id = ?'
            rows = [dict(r) for r in c.execute(
                f'SELECT * FROM storage_containers {where} '
                'ORDER BY pos_row, pos_col, id', params)]
            direct = self._direct_item_counts(c)

        by_id = {r['id']: r for r in rows}
        for r in rows:
            r['children'] = []
            r['item_count'] = direct.get(r['id'], 0)

        roots_by_unit = {}
        for r in rows:
            if r['parent_id'] is None:
                roots_by_unit.setdefault(r['unit_id'], []).append(r)
            else:
                parent = by_id.get(r['parent_id'])
                if parent is not None:
                    parent['children'].append(r)
                else:
                    # Defensive: a dangling parent_id would otherwise hide the
                    # container entirely. Surface it at the top instead.
                    r['orphaned'] = True
                    roots_by_unit.setdefault(r['unit_id'], []).append(r)

        def totals(node):
            node['subtree_item_count'] = node['item_count'] + sum(
                totals(ch) for ch in node['children'])
            node['child_count'] = len(node['children'])
            return node['subtree_item_count']

        out = []
        for u in units:
            u = dict(u)
            u['containers'] = roots_by_unit.get(u['id'], [])
            for root in u['containers']:
                totals(root)
            u['item_count'] = sum(r['subtree_item_count'] for r in u['containers'])
            u['container_count'] = sum(1 for r in rows if r['unit_id'] == u['id'])
            out.append(u)
        return out

    def flat_list(self):
        """Every container with its full path precomputed.

        One request serves both the location picker and the Location column in
        the records table, instead of a path lookup per row.
        """
        out = []
        for unit in self.get_tree():
            def walk(node, prefix):
                here = prefix + [node['label']]
                out.append({
                    'id': node['id'],
                    'unit_id': unit['id'],
                    'unit_name': unit['name'],
                    'kind': node['kind'],
                    'label': node['label'],
                    'path': ' > '.join(here),
                    'full_path': f"{unit['name']} > {' > '.join(here)}",
                    'depth': len(here) - 1,
                    'temp_c': node['temp_c'] if node['temp_c'] is not None
                              else unit['default_temp_c'],
                    'temp_is_override': node['temp_c'] is not None,
                    'owner_lab': node['owner_lab'],
                    # Physical arrangement of this container's children, and
                    # this container's own slot inside its parent.
                    'grid_rows': node['grid_rows'],
                    'grid_cols': node['grid_cols'],
                    'pos_row': node['pos_row'],
                    'pos_col': node['pos_col'],
                    'item_count': node['item_count'],
                    'subtree_item_count': node['subtree_item_count'],
                    'child_count': node['child_count'],
                })
                for child in node['children']:
                    walk(child, here)
            for root in unit['containers']:
                walk(root, [])
        return out

    def path(self, container_id):
        """Breadcrumb from unit down to this container."""
        node = self.get_container(container_id)
        parts, cur = [], node
        with self._conn() as c:
            while cur is not None:
                parts.append({'id': cur['id'], 'label': cur['label'],
                              'kind': cur['kind']})
                if cur['parent_id'] is None:
                    break
                row = c.execute('SELECT * FROM storage_containers WHERE id = ?',
                                (cur['parent_id'],)).fetchone()
                cur = dict(row) if row else None
        unit = self.get_unit(node['unit_id'])
        return {'unit': {'id': unit['id'], 'name': unit['name']},
                'containers': list(reversed(parts))}

    def container_items(self, container_id, include_descendants=False):
        self.get_container(container_id)
        with self._conn() as c:
            ids = (self._subtree_ids(c, container_id) if include_descendants
                   else [container_id])
            placeholders = ','.join('?' * len(ids))
            items = []
            for table, name_col in ITEM_TABLES:
                for r in c.execute(
                        f'SELECT id, "{name_col}" AS name, container_id FROM {table}'
                        f' WHERE container_id IN ({placeholders}) ORDER BY "{name_col}"',
                        ids):
                    items.append({'table': table, 'id': r['id'],
                                  'name': r['name'],
                                  'container_id': r['container_id']})
        return items

    def unplaced_items(self):
        with self._conn() as c:
            items = []
            for table, name_col in ITEM_TABLES:
                for r in c.execute(
                        f'SELECT id, "{name_col}" AS name FROM {table}'
                        f' WHERE container_id IS NULL ORDER BY "{name_col}"'):
                    items.append({'table': table, 'id': r['id'], 'name': r['name']})
        return items

    def place_item(self, table, item_id, container_id):
        if table not in dict(ITEM_TABLES):
            raise StorageError(f'Unknown item table {table!r}')
        if container_id is not None:
            self.get_container(container_id)
        with self._conn() as c:
            cur = c.execute(f'UPDATE {table} SET container_id = ? WHERE id = ?',
                            (container_id, item_id))
            if cur.rowcount == 0:
                raise StorageError(f'No {table} row with id {item_id}')
        return True

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _subtree_ids(conn, container_id):
        """The container plus every descendant, via recursive CTE."""
        rows = conn.execute('''
            WITH RECURSIVE sub(id) AS (
                SELECT id FROM storage_containers WHERE id = ?
                UNION ALL
                SELECT sc.id FROM storage_containers sc JOIN sub ON sc.parent_id = sub.id
            ) SELECT id FROM sub''', (container_id,)).fetchall()
        return [r['id'] for r in rows]

    @staticmethod
    def _direct_item_counts(conn):
        counts = {}
        for table, _ in ITEM_TABLES:
            for r in conn.execute(
                    f'SELECT container_id, COUNT(*) n FROM {table}'
                    ' WHERE container_id IS NOT NULL GROUP BY container_id'):
                counts[r['container_id']] = counts.get(r['container_id'], 0) + r['n']
        return counts

    @staticmethod
    def _count_items(conn, container_ids):
        if not container_ids:
            return 0
        placeholders = ','.join('?' * len(container_ids))
        total = 0
        for table, _ in ITEM_TABLES:
            total += conn.execute(
                f'SELECT COUNT(*) n FROM {table} WHERE container_id IN'
                f' ({placeholders})', container_ids).fetchone()['n']
        return total

    @staticmethod
    def _move_items(conn, container_ids, new_container_id):
        if not container_ids:
            return 0
        placeholders = ','.join('?' * len(container_ids))
        moved = 0
        for table, _ in ITEM_TABLES:
            cur = conn.execute(
                f'UPDATE {table} SET container_id = ? WHERE container_id IN'
                f' ({placeholders})', [new_container_id] + list(container_ids))
            moved += cur.rowcount
        return moved

    @classmethod
    def _unplace_items(cls, conn, container_ids):
        return cls._move_items(conn, container_ids, None)

    def _next_position(self, parent_id, unit_id, axis):
        """Next free slot among a parent's children, along the given axis."""
        field = 'pos_col' if axis == 'col' else 'pos_row'
        with self._conn() as c:
            if parent_id is None:
                row = c.execute(
                    f'SELECT MAX({field}) m FROM storage_containers'
                    ' WHERE parent_id IS NULL AND unit_id = ?', (unit_id,)).fetchone()
            else:
                row = c.execute(
                    f'SELECT MAX({field}) m FROM storage_containers'
                    ' WHERE parent_id = ?', (parent_id,)).fetchone()
        nxt = 0 if row['m'] is None else row['m'] + 1
        return (nxt, 0) if axis == 'row' else (0, nxt)


def _num(value):
    """Permissive numeric coercion: '' and None both mean 'not set'."""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise StorageError(f'{value!r} is not a number')


def _label_for(index, scheme):
    """0 -> 'A' or '1'. Past 'Z' it continues AA, AB, ... """
    if scheme == 'numbers':
        return str(index + 1)
    label, n = '', index
    while True:
        label = chr(ord('A') + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            return label
