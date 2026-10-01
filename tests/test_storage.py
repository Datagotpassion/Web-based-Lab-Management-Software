"""Tests for the storage container tree.

Focus is on the things a tree gets wrong: cycles, cascading deletes that lose
items, and -- the reason this exists -- whether genuinely irregular physical
layouts can be represented without fighting the model.
"""

import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from migrate_containers import DDL
from storage import StorageError, StorageTree, _label_for


@pytest.fixture
def tree():
    """A StorageTree over a throwaway database with the full schema."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    Database(path)  # creates drugs / antibodies / settings
    st = StorageTree(path)
    with st._conn() as c:
        c.executescript(DDL)
        for table in ('drugs', 'primary_antibodies', 'secondary_antibodies'):
            cols = [r[1] for r in c.execute(f'PRAGMA table_info({table})')]
            if 'container_id' not in cols:
                c.execute(f'ALTER TABLE {table} ADD COLUMN container_id INTEGER')

    yield st

    if os.path.exists(path):
        os.remove(path)


def add_drug(tree, name, container_id=None):
    with tree._conn() as c:
        cur = c.execute('INSERT INTO drugs (drug_name, container_id) VALUES (?,?)',
                        (name, container_id))
        return cur.lastrowid


# --------------------------------------------------------------- irregularity

class TestIrregularLayouts:
    """The whole point: the freezer is not a uniform grid."""

    def test_shelves_can_have_different_rack_counts(self, tree):
        unit = tree.create_unit('-80 Freezer', kind='ultralow', default_temp_c=-80)
        body = tree.create_container(unit['id'], None, 'section', 'Body')

        for shelf_no, n_racks in [(1, 3), (2, 4), (3, 5), (4, 0)]:
            shelf = tree.create_container(unit['id'], body['id'], 'shelf',
                                          f'Shelf {shelf_no}')
            if n_racks:
                tree.bulk_create_children(shelf['id'], 'rack', n_racks)

        [u] = tree.get_tree(unit['id'])
        shelves = u['containers'][0]['children']
        assert [s['child_count'] for s in shelves] == [3, 4, 5, 0]

    def test_unit_with_no_door_and_unit_with_several(self, tree):
        plain = tree.create_unit('-20 Freezer', kind='freezer', default_temp_c=-20)
        tree.create_container(plain['id'], None, 'section', 'Body')

        combo = tree.create_unit('Combo fridge', kind='fridge', default_temp_c=4)
        for label, temp in [('Body', 4), ('Upper door', 4), ('Freezer door', -20)]:
            tree.create_container(combo['id'], None, 'section', label, temp_c=temp)

        assert len(tree.get_tree(plain['id'])[0]['containers']) == 1
        sections = tree.get_tree(combo['id'])[0]['containers']
        assert len(sections) == 3
        # A section may run at a different temperature from its appliance.
        assert sorted(s['temp_c'] for s in sections) == [-20.0, 4.0, 4.0]

    def test_nesting_depth_is_not_fixed(self, tree):
        unit = tree.create_unit('Deep freezer')
        node = tree.create_container(unit['id'], None, 'section', 'Body')
        for kind, label in [('shelf', 'Shelf 1'), ('rack', 'A'),
                            ('box', 'Box 1'), ('tray', 'Tray 1')]:
            node = tree.create_container(unit['id'], node['id'], kind, label)
        path = tree.path(node['id'])
        assert [p['label'] for p in path['containers']] == [
            'Body', 'Shelf 1', 'A', 'Box 1', 'Tray 1']


# -------------------------------------------------------------------- cycles

class TestCyclePrevention:
    def test_cannot_be_own_parent(self, tree):
        unit = tree.create_unit('U')
        node = tree.create_container(unit['id'], None, 'section', 'Body')
        with pytest.raises(StorageError, match='own parent'):
            tree.move_container(node['id'], node['id'])

    def test_cannot_move_into_own_descendant(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelf = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 1')
        rack = tree.create_container(unit['id'], shelf['id'], 'rack', 'A')

        with pytest.raises(StorageError, match='descendant'):
            tree.move_container(body['id'], rack['id'])

        # The tree is unchanged after the refusal.
        assert tree.get_container(body['id'])['parent_id'] is None

    def test_legitimate_reparent_still_works(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        s1 = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 1')
        s2 = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 2')
        rack = tree.create_container(unit['id'], s1['id'], 'rack', 'A')

        tree.move_container(rack['id'], s2['id'])
        assert tree.get_container(rack['id'])['parent_id'] == s2['id']


# ------------------------------------------------------------------- deletes

class TestDeletion:
    def test_delete_refuses_when_items_inside(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelf = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 2')
        rack = tree.create_container(unit['id'], shelf['id'], 'rack', 'B')
        add_drug(tree, 'BMP4', rack['id'])

        with pytest.raises(StorageError, match='1 item'):
            tree.delete_container(shelf['id'])
        # Nothing was removed.
        assert tree.get_container(rack['id'])['id'] == rack['id']

    def test_forced_delete_moves_items_up_rather_than_losing_them(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelf = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 2')
        rack = tree.create_container(unit['id'], shelf['id'], 'rack', 'B')
        drug_id = add_drug(tree, 'BMP4', rack['id'])

        result = tree.delete_container(shelf['id'], force=True)
        assert result['removed_containers'] == 2  # shelf + rack
        assert result['moved_items'] == 1

        # The drug survived and now sits in the deleted shelf's parent.
        with tree._conn() as c:
            row = c.execute('SELECT container_id FROM drugs WHERE id = ?',
                            (drug_id,)).fetchone()
        assert row['container_id'] == body['id']

    def test_delete_removes_whole_subtree(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelf = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 1')
        racks = tree.bulk_create_children(shelf['id'], 'rack', 4)
        for r in racks:
            tree.bulk_create_children(r['id'], 'box', 3, scheme='numbers',
                                      prefix='Box ')

        result = tree.delete_container(shelf['id'])
        assert result['removed_containers'] == 1 + 4 + 12
        assert tree.get_tree(unit['id'])[0]['container_count'] == 1  # just Body

    def test_delete_unit_unplaces_its_items(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        drug_id = add_drug(tree, 'Orphan me', body['id'])

        result = tree.delete_unit(unit['id'])
        assert result['unplaced_items'] == 1

        # The drug still exists, just with no location.
        with tree._conn() as c:
            row = c.execute('SELECT container_id FROM drugs WHERE id = ?',
                            (drug_id,)).fetchone()
        assert row['container_id'] is None
        assert [i['name'] for i in tree.unplaced_items()] == ['Orphan me']

    def test_no_containers_survive_a_unit_delete(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        tree.bulk_create_children(body['id'], 'shelf', 5)
        tree.delete_unit(unit['id'])
        with tree._conn() as c:
            assert c.execute('SELECT COUNT(*) n FROM storage_containers'
                             ).fetchone()['n'] == 0


# ------------------------------------------------------------------ bulk add

class TestBulkCreate:
    def test_letters_and_numbers(self, tree):
        unit = tree.create_unit('U')
        shelf = tree.create_container(unit['id'], None, 'shelf', 'Shelf 1')

        racks = tree.bulk_create_children(shelf['id'], 'rack', 4)
        assert [r['label'] for r in racks] == ['A', 'B', 'C', 'D']

        rack_a = racks[0]
        boxes = tree.bulk_create_children(rack_a['id'], 'box', 3,
                                          scheme='numbers', prefix='Box ')
        assert [b['label'] for b in boxes] == ['Box 1', 'Box 2', 'Box 3']

    def test_racks_lay_out_across_and_boxes_stack_down(self, tree):
        unit = tree.create_unit('U')
        shelf = tree.create_container(unit['id'], None, 'shelf', 'Shelf 1')
        racks = tree.bulk_create_children(shelf['id'], 'rack', 3)
        assert [r['pos_col'] for r in racks] == [0, 1, 2]
        assert {r['pos_row'] for r in racks} == {0}

        boxes = tree.bulk_create_children(racks[0]['id'], 'box', 3,
                                          scheme='numbers', prefix='Box ')
        assert [b['pos_row'] for b in boxes] == [0, 1, 2]

    def test_second_bulk_add_appends_rather_than_overlapping(self, tree):
        unit = tree.create_unit('U')
        shelf = tree.create_container(unit['id'], None, 'shelf', 'Shelf 1')
        tree.bulk_create_children(shelf['id'], 'rack', 2)
        more = tree.bulk_create_children(shelf['id'], 'rack', 2)
        assert [r['pos_col'] for r in more] == [2, 3]

    def test_label_scheme_continues_past_z(self):
        assert _label_for(0, 'letters') == 'A'
        assert _label_for(25, 'letters') == 'Z'
        assert _label_for(26, 'letters') == 'AA'
        assert _label_for(27, 'letters') == 'AB'

    def test_rejects_silly_counts(self, tree):
        unit = tree.create_unit('U')
        shelf = tree.create_container(unit['id'], None, 'shelf', 'Shelf 1')
        for bad in (0, -1, 101):
            with pytest.raises(StorageError, match='between 1 and 100'):
                tree.bulk_create_children(shelf['id'], 'rack', bad)


# -------------------------------------------------------------------- counts

class TestCounts:
    def test_subtree_counts_roll_up(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelf = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 2')
        racks = tree.bulk_create_children(shelf['id'], 'rack', 3)
        for rack, n in zip(racks, [14, 7, 5]):
            for i in range(n):
                add_drug(tree, f'drug {rack["label"]}{i}', rack['id'])

        [u] = tree.get_tree(unit['id'])
        body_node = u['containers'][0]
        shelf_node = body_node['children'][0]

        assert body_node['item_count'] == 0           # nothing directly in Body
        assert shelf_node['subtree_item_count'] == 26  # 14 + 7 + 5
        assert [r['item_count'] for r in shelf_node['children']] == [14, 7, 5]
        assert u['item_count'] == 26

    def test_items_from_all_three_tables_are_counted(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        add_drug(tree, 'a drug', body['id'])
        with tree._conn() as c:
            c.execute('INSERT INTO primary_antibodies (name, container_id) '
                      'VALUES (?,?)', ('anti-TNNT2', body['id']))
            c.execute('INSERT INTO secondary_antibodies (name, container_id) '
                      'VALUES (?,?)', ('goat anti-rabbit', body['id']))

        [u] = tree.get_tree(unit['id'])
        assert u['containers'][0]['item_count'] == 3


# ---------------------------------------------------------------- robustness

class TestRobustness:
    def test_cross_unit_move_takes_the_subtree_along(self, tree):
        a = tree.create_unit('Unit A')
        b = tree.create_unit('Unit B')
        body_a = tree.create_container(a['id'], None, 'section', 'Body')
        shelf = tree.create_container(a['id'], body_a['id'], 'shelf', 'Shelf 1')
        racks = tree.bulk_create_children(shelf['id'], 'rack', 2)
        body_b = tree.create_container(b['id'], None, 'section', 'Body')

        tree.move_container(shelf['id'], body_b['id'])

        # The shelf and both racks now belong to unit B.
        for cid in [shelf['id']] + [r['id'] for r in racks]:
            assert tree.get_container(cid)['unit_id'] == b['id']

    def test_child_cannot_be_created_under_a_foreign_parent(self, tree):
        a = tree.create_unit('Unit A')
        b = tree.create_unit('Unit B')
        body_a = tree.create_container(a['id'], None, 'section', 'Body')
        with pytest.raises(StorageError, match='different storage unit'):
            tree.create_container(b['id'], body_a['id'], 'shelf', 'Shelf 1')

    def test_dangling_parent_is_surfaced_not_hidden(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelf = tree.create_container(unit['id'], body['id'], 'shelf', 'Shelf 1')

        # Point at a parent that does not exist. StorageTree's own connections
        # set PRAGMA foreign_keys = ON and would reject this, but database.py
        # does not, so this is reachable in practice -- hence the defensive
        # handling in get_tree that this test covers.
        raw = sqlite3.connect(tree.db_path)
        raw.execute('UPDATE storage_containers SET parent_id = 9999 WHERE id = ?',
                    (shelf['id'],))
        raw.commit()
        raw.close()

        [u] = tree.get_tree(unit['id'])
        surfaced = [ct for ct in u['containers'] if ct.get('orphaned')]
        assert len(surfaced) == 1 and surfaced[0]['label'] == 'Shelf 1'

    def test_reorder_at_the_edge_is_a_no_op(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelves = tree.bulk_create_children(body['id'], 'shelf', 3)

        tree.reorder(shelves[0]['id'], 'up')  # already first
        [u] = tree.get_tree(unit['id'])
        assert [s['label'] for s in u['containers'][0]['children']] == \
            ['A', 'B', 'C']

    def test_reorder_swaps_neighbours(self, tree):
        unit = tree.create_unit('U')
        body = tree.create_container(unit['id'], None, 'section', 'Body')
        shelves = tree.bulk_create_children(body['id'], 'shelf', 3)

        tree.reorder(shelves[0]['id'], 'down')
        [u] = tree.get_tree(unit['id'])
        assert [s['label'] for s in u['containers'][0]['children']] == \
            ['B', 'A', 'C']

    def test_blank_labels_and_names_rejected(self, tree):
        with pytest.raises(StorageError, match='needs a name'):
            tree.create_unit('   ')
        unit = tree.create_unit('U')
        with pytest.raises(StorageError, match='needs a label'):
            tree.create_container(unit['id'], None, 'section', '  ')

    def test_temperature_accepts_blank_as_unset_and_rejects_nonsense(self, tree):
        unit = tree.create_unit('U', default_temp_c='')
        assert unit['default_temp_c'] is None
        with pytest.raises(StorageError, match='not a number'):
            tree.create_unit('V', default_temp_c='quite cold')

    def test_missing_ids_raise_rather_than_returning_none(self, tree):
        with pytest.raises(StorageError, match='No storage unit'):
            tree.get_unit(9999)
        with pytest.raises(StorageError, match='No container'):
            tree.get_container(9999)
