"""Create a demonstration database with invented contents.

A clone of this repository has no database, and real lab data does not belong
in version control -- so this builds one that shows what the system is for:
a -80 C freezer laid out as shelves, racks and 4x4 position matrices, a fridge
and a freezer alongside it, reagents placed down to a position, and a few
antibodies for the panel designer.

Everything here is fictional. Catalogue numbers are illustrative.

    python examples/seed_example_data.py                 # -> example.db
    python examples/seed_example_data.py --db demo.db
    LABMANAGER_DB=example.db python serve.py             # then run against it
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import history                      # noqa: E402
from database import Database       # noqa: E402
from storage import StorageTree     # noqa: E402

# (name, concentration, unit, aliquot, supplier, catalogue, rack, position)
REAGENTS = [
    ('CHIR-99021',        10,   'mM',    '30 µL',  'Example Bio',  'EX-4423',  'B', 1),
    ('Y-27632',           10,   'mM',    '50 µL',  'Example Bio',  'EX-1254',  'B', 2),
    ('SB-431542',         10,   'mM',    '25 µL',  'Example Bio',  'EX-1041',  'B', 5),
    ('LDN-193189',        5,    'mM',    '25 µL',  'Example Bio',  'EX-6053',  'B', 6),
    ('Activin A',         100,  'µg/mL', '20 µL',  'Demo Proteins', 'DP-338',  'C', 1),
    ('BMP4',              50,   'µg/mL', '20 µL',  'Demo Proteins', 'DP-314',  'C', 2),
    ('FGF-2',             100,  'µg/mL', '50 µL',  'Demo Proteins', 'DP-233',  'C', 3),
    ('VEGF-165',          50,   'µg/mL', '25 µL',  'Demo Proteins', 'DP-293',  'C', 7),
    ('IWR-1',             10,   'mM',    '30 µL',  'Example Bio',  'EX-3533',  'D', 1),
    ('Insulin, human',    10,   'mg/mL', '500 µL', 'Demo Proteins', 'DP-019',  'D', 4),
    # Recorded only to a rack, as things often are before anyone sorts them.
    ('Ascorbic acid',     50,   'mM',    '1 mL',   'Example Bio',  'EX-0417',  'A', None),
    ('Thiazovivin',       10,   'mM',    '30 µL',  'Example Bio',  'EX-9387',  'A', None),
]

PRIMARIES = [
    ('anti-TNNT2',  'TNNT2',   'Mouse',  'Monoclonal', 'IgG1', 'Example Bio', '-20C'),
    ('anti-NKX2-5', 'NKX2-5',  'Rabbit', 'Polyclonal', 'IgG',  'Example Bio', '-20C'),
    ('anti-SOX17',  'SOX17',   'Goat',   'Polyclonal', 'IgG',  'Demo Proteins', '-20C'),
    ('anti-OCT4',   'POU5F1',  'Rabbit', 'Monoclonal', 'IgG',  'Example Bio', '-20C'),
]

SECONDARIES = [
    ('Donkey anti-Mouse AF488',  'Mouse',  'IgG (H+L)', 'Donkey', 'Alexa Fluor 488'),
    ('Donkey anti-Rabbit AF594', 'Rabbit', 'IgG (H+L)', 'Donkey', 'Alexa Fluor 594'),
    ('Donkey anti-Goat AF647',   'Goat',   'IgG (H+L)', 'Donkey', 'Alexa Fluor 647'),
]

BLANK = {k: None for k in (
    'stock_concentration', 'stock_unit', 'storage_temp', 'supplier',
    'preparation_date', 'notes', 'solvents', 'solubility', 'light_sensitive',
    'preparation_time', 'expiration_time', 'sterility', 'lot_number',
    'product_number', 'container_id', 'aliquot_volume', 'product_url')}


def build(db_path):
    db = Database(db_path)
    st = StorageTree(db_path).ensure_schema()
    conn = db.get_connection()
    try:
        history.ensure(conn)
    finally:
        conn.close()

    # --- the -80: 5 shelves, 4 racks each, every rack a 4x4 position matrix
    freezer = st.create_unit('-80 °C Freezer', kind='ultralow',
                             room='Example Lab', default_temp_c=-80)
    body = st.create_container(freezer['id'], None, 'section', 'Body')
    racks = {}
    for shelf_no in range(1, 6):
        shelf = st.create_container(freezer['id'], body['id'], 'shelf',
                                    f'Shelf {shelf_no}')
        for rack in st.bulk_create_children(shelf['id'], 'rack', 4):
            if shelf_no == 2:
                racks[rack['label']] = rack

    # --- a fridge and a freezer, to show units differ in shape
    fridge = st.create_unit('4 °C Fridge', kind='fridge',
                            room='Example Lab', default_temp_c=4)
    f_body = st.create_container(fridge['id'], None, 'section', 'Body')
    st.bulk_create_children(f_body['id'], 'shelf', 4, scheme='numbers',
                            prefix='Shelf ')
    f_door = st.create_container(fridge['id'], None, 'section', 'Door')
    st.bulk_create_children(f_door['id'], 'bin', 3, scheme='numbers',
                            prefix='Bin ')

    minus20 = st.create_unit('-20 °C Freezer', kind='freezer',
                             room='Example Lab', default_temp_c=-20)
    m_body = st.create_container(minus20['id'], None, 'section', 'Body')
    st.bulk_create_children(m_body['id'], 'shelf', 3, scheme='numbers',
                            prefix='Shelf ')

    # --- positions, created only where something is stored
    positions = {}
    for _, _, _, _, _, _, rack_label, slot in REAGENTS:
        if slot is None:
            continue
        key = (rack_label, slot)
        if key in positions:
            continue
        rack = racks[rack_label]
        cols = rack['grid_cols'] or 4
        positions[key] = st.create_container(
            freezer['id'], rack['id'], 'box', f'Box {slot}',
            pos_row=(slot - 1) // cols, pos_col=(slot - 1) % cols)

    for name, conc, unit, aliquot, supplier, cat, rack_label, slot in REAGENTS:
        where = (positions[(rack_label, slot)] if slot is not None
                 else racks[rack_label])
        db.add_record({**BLANK, 'drug_name': name, 'stock_concentration': conc,
                       'stock_unit': unit, 'aliquot_volume': aliquot,
                       'storage_temp': '-80C', 'supplier': supplier,
                       'product_number': cat, 'container_id': where['id']})

    conn = db.get_connection()
    try:
        for name, target, host, clonality, isotype, supplier, temp in PRIMARIES:
            conn.execute(
                'INSERT INTO primary_antibodies (name, target_protein,'
                ' host_species, clonality, isotype, supplier, storage_temp)'
                ' VALUES (?,?,?,?,?,?,?)',
                (name, target, host, clonality, isotype, supplier, temp))
        for name, target_sp, target_iso, host, conjugate in SECONDARIES:
            conn.execute(
                'INSERT INTO secondary_antibodies (name, target_species,'
                ' target_isotype, host_species, conjugate, storage_temp)'
                ' VALUES (?,?,?,?,?,?)',
                (name, target_sp, target_iso, host, conjugate, '4C'))
        conn.execute("UPDATE settings SET value='Example Lab' WHERE key='lab_name'")
        conn.execute("UPDATE settings SET value='Demo' WHERE key='pi_name'")
        conn.commit()
    finally:
        conn.close()

    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default='example.db',
                    help='file to create (default example.db)')
    ap.add_argument('--force', action='store_true',
                    help='overwrite an existing file')
    args = ap.parse_args()

    path = Path(args.db)
    if path.exists():
        if not args.force:
            raise SystemExit(f'{path} already exists; pass --force to replace it.')
        path.unlink()

    st = build(str(path))
    units = st.get_tree()
    print(f'  created {path}')
    for u in units:
        print(f'    {u["name"]}: {u["container_count"]} containers, '
              f'{u["item_count"]} items')
    print()
    print(f'  try it with:  LABMANAGER_DB={path} python serve.py')


if __name__ == '__main__':
    main()
