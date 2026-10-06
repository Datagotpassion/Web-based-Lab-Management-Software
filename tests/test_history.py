"""Tests for point-in-time record history.

The property that matters is completeness: history implemented as triggers
should record a change made by any route, including one the application does
not know about. Hooks in application code would only cover remembered paths.
"""

import json
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import history
from database import Database


BLANK = {k: None for k in (
    'stock_concentration', 'stock_unit', 'storage_temp', 'supplier',
    'preparation_date', 'notes', 'solvents', 'solubility', 'light_sensitive',
    'preparation_time', 'expiration_time', 'sterility', 'lot_number',
    'product_number', 'container_id', 'aliquot_volume', 'product_url')}


@pytest.fixture
def tracked():
    """A database with history triggers installed."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = Database(path)
    conn = sqlite3.connect(path)
    history.ensure(conn)
    yield db, conn
    conn.close()
    if os.path.exists(path):
        os.remove(path)


class TestNothingEscapes:
    def test_create_update_delete_are_all_recorded(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4'})
        db.update_record(rid, {**BLANK, 'drug_name': 'BMP4', 'supplier': 'R&D'})
        db.delete_record(rid)
        actions = [e['action'] for e in history.for_record(conn, 'drugs', rid)]
        assert actions == ['delete', 'update', 'create']

    def test_a_write_the_application_knows_nothing_about_is_recorded(self, tracked):
        """The reason this is triggers and not hooks."""
        db, conn = tracked
        conn.execute("INSERT INTO drugs (drug_name) VALUES ('snuck in')")
        conn.commit()
        entries = history.recent(conn)
        assert any(e['snapshot']['drug_name'] == 'snuck in' for e in entries)

    def test_snapshot_holds_the_whole_row(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4',
                             'supplier': 'R&D', 'stock_concentration': 10.0})
        snap = history.for_record(conn, 'drugs', rid)[0]['snapshot']
        assert snap['drug_name'] == 'BMP4'
        assert snap['supplier'] == 'R&D'
        assert snap['stock_concentration'] == 10.0

    def test_a_new_column_is_picked_up_when_triggers_are_rebuilt(self, tracked):
        db, conn = tracked
        conn.execute('ALTER TABLE drugs ADD COLUMN hazard TEXT')
        history.ensure(conn)          # as startup does
        conn.execute("INSERT INTO drugs (drug_name, hazard) VALUES ('X','toxic')")
        conn.commit()
        snap = history.recent(conn)[0]['snapshot']
        assert snap['hazard'] == 'toxic'


class TestRestore:
    def test_a_deleted_record_can_be_put_back_as_it_was(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4', 'supplier': 'R&D'})
        db.update_record(rid, {**BLANK, 'drug_name': 'BMP4',
                               'supplier': 'R&D Systems'})
        db.delete_record(rid)

        [entry] = history.deleted(conn)
        result = history.restore(conn, entry['history_id'])

        assert result['reused_original_id'] is True
        row = conn.execute(
            'SELECT drug_name, supplier FROM drugs WHERE id = ?', (rid,)).fetchone()
        # Restored to its state at deletion, not its original state.
        assert row == ('BMP4', 'R&D Systems')

    def test_restoring_keeps_the_original_id_so_references_still_resolve(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4', 'container_id': 42})
        db.delete_record(rid)
        [entry] = history.deleted(conn)
        result = history.restore(conn, entry['history_id'])
        assert result['id'] == rid
        held = conn.execute('SELECT container_id FROM drugs WHERE id = ?',
                            (rid,)).fetchone()[0]
        assert held == 42

    def test_an_occupied_id_gets_a_new_one_rather_than_overwriting(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'First'})
        db.delete_record(rid)
        # Capture the deletion before anything else touches that id: once the
        # id is occupied again the record is no longer "deleted", which is
        # correct, so the entry has to be taken first.
        [entry] = history.deleted(conn)

        # AUTOINCREMENT means sqlite never reissues an id, so this only happens
        # if something inserts one explicitly -- but restore must still refuse
        # to overwrite whatever is there.
        conn.execute('INSERT INTO drugs (id, drug_name) VALUES (?, ?)',
                     (rid, 'Someone else'))
        conn.commit()

        result = history.restore(conn, entry['history_id'])
        assert result['reused_original_id'] is False
        assert result['id'] != rid
        # The occupant is untouched.
        assert conn.execute('SELECT drug_name FROM drugs WHERE id = ?',
                            (rid,)).fetchone()[0] == 'Someone else'

    def test_only_the_latest_deletion_is_offered(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4'})
        db.delete_record(rid)
        [entry] = history.deleted(conn)
        history.restore(conn, entry['history_id'])
        # Now live again, so it should no longer be listed as restorable.
        assert history.deleted(conn) == []


class TestDescribe:
    def test_names_the_fields_that_changed(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4'})
        db.update_record(rid, {**BLANK, 'drug_name': 'BMP4',
                               'supplier': 'R&D', 'lot_number': 'L1'})
        entries = history.for_record(conn, 'drugs', rid)
        summary = history.describe(entries[0], entries[1])
        assert 'supplier' in summary and 'lot_number' in summary

    def test_create_and_delete_are_stated_plainly(self, tracked):
        db, conn = tracked
        rid = db.add_record({**BLANK, 'drug_name': 'BMP4'})
        db.delete_record(rid)
        entries = history.for_record(conn, 'drugs', rid)
        assert history.describe(entries[-1]) == 'created'
        assert history.describe(entries[0]) == 'deleted'
