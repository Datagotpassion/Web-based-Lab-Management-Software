"""
Database operations module for Lab Management System
Handles all SQLite database interactions
"""

import sqlite3
import os
from datetime import datetime


class Database:
    def __init__(self, db_path='lab_management.db'):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Create and return a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def init_database(self):
        """Initialize database with required tables and columns"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create main drugs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_name TEXT NOT NULL,
                stock_concentration REAL,
                stock_unit TEXT,
                storage_temp TEXT,
                supplier TEXT,
                preparation_date TEXT,
                notes TEXT,
                solvents TEXT,
                solubility TEXT,
                light_sensitive TEXT,
                preparation_time TEXT,
                expiration_time TEXT,
                sterility TEXT,
                lot_number TEXT,
                product_number TEXT,
                storage_section TEXT,
                storage_row INTEGER,
                storage_column INTEGER
            )
        ''')

        # Add storage location columns if they don't exist
        existing_columns = [col[1] for col in cursor.execute("PRAGMA table_info(drugs)").fetchall()]
        new_columns = [
            ('storage_section', 'TEXT'),
            ('storage_row', 'INTEGER'),
            ('storage_column', 'INTEGER'),
            ('fridge_region_id', 'INTEGER'),  # New: link to visual region
            ('aliquot_volume', 'TEXT')  # New: aliquot volume (e.g., "50 µL", "1 mL")
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cursor.execute(f'ALTER TABLE drugs ADD COLUMN {col_name} {col_type}')

        # Create fridge layouts table (stores photos)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fridge_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temp_key TEXT NOT NULL,
                section TEXT NOT NULL,
                photo_filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(temp_key, section)
            )
        ''')

        # Create fridge regions table (stores clickable regions on photos)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fridge_regions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id INTEGER NOT NULL,
                region_name TEXT NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layout_id) REFERENCES fridge_layouts(id) ON DELETE CASCADE
            )
        ''')

        # Create schematic layouts table (stores digital layout structure)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fridge_schematic_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temp_key TEXT NOT NULL,
                section TEXT NOT NULL,
                layout_name TEXT,
                reference_photo TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(temp_key, section)
            )
        ''')

        # Create schematic zones table (stores individual zones in a layout)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fridge_schematic_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id INTEGER NOT NULL,
                zone_name TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                col_index INTEGER NOT NULL,
                col_span INTEGER DEFAULT 1,
                row_span INTEGER DEFAULT 1,
                color TEXT DEFAULT '#e3f2fd',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layout_id) REFERENCES fridge_schematic_layouts(id) ON DELETE CASCADE
            )
        ''')

        # Create fridge configuration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fridge_config (
                temp_key TEXT PRIMARY KEY,
                body_rows INTEGER DEFAULT 3,
                body_columns INTEGER DEFAULT 3,
                door_rows INTEGER DEFAULT 2,
                door_columns INTEGER DEFAULT 2
            )
        ''')

        # Initialize default fridge configurations
        default_configs = [
            ('4C', 3, 3, 2, 2),
            ('-20C', 3, 3, 2, 2),
            ('-80C', 3, 3, 0, 0)  # -80C has no door storage
        ]

        for temp_key, body_rows, body_cols, door_rows, door_cols in default_configs:
            cursor.execute('''
                INSERT OR IGNORE INTO fridge_config (temp_key, body_rows, body_columns, door_rows, door_columns)
                VALUES (?, ?, ?, ?, ?)
            ''', (temp_key, body_rows, body_cols, door_rows, door_cols))

        # Create settings table for lab configuration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Initialize default settings
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES ('lab_name', '')
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES ('pi_name', '')
        ''')

        # Create primary antibodies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS primary_antibodies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_protein TEXT,
                host_species TEXT,
                clonality TEXT,
                isotype TEXT,
                clone_number TEXT,
                supplier TEXT,
                catalog_number TEXT,
                lot_number TEXT,
                applications TEXT,
                fixation_compatibility TEXT,
                dilution_if TEXT,
                dilution_wb TEXT,
                dilution_ihc TEXT,
                storage_temp TEXT,
                stock_concentration TEXT,
                aliquot_volume TEXT,
                validated TEXT,
                notes TEXT,
                fridge_region_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create secondary antibodies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS secondary_antibodies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_species TEXT,
                target_isotype TEXT,
                host_species TEXT,
                format TEXT,
                conjugate TEXT,
                fluorophore_excitation TEXT,
                fluorophore_emission TEXT,
                cross_adsorbed TEXT,
                cross_adsorbed_against TEXT,
                supplier TEXT,
                catalog_number TEXT,
                lot_number TEXT,
                applications TEXT,
                dilution_if TEXT,
                dilution_wb TEXT,
                dilution_ihc TEXT,
                storage_temp TEXT,
                stock_concentration TEXT,
                aliquot_volume TEXT,
                notes TEXT,
                fridge_region_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def get_all_records(self):
        """Retrieve all records from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM drugs ORDER BY id DESC')
        records = cursor.fetchall()
        conn.close()
        return records

    def get_record_by_id(self, record_id):
        """Retrieve a single record by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM drugs WHERE id = ?', (record_id,))
        record = cursor.fetchone()
        conn.close()
        return record

    def add_record(self, data):
        """Add a new record to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO drugs (
                drug_name, stock_concentration, stock_unit, storage_temp,
                supplier, preparation_date, notes, solvents, solubility,
                light_sensitive, preparation_time, expiration_time, sterility,
                lot_number, product_number, storage_section, storage_row, storage_column,
                aliquot_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['drug_name'],
            data['stock_concentration'],
            data['stock_unit'],
            data['storage_temp'],
            data['supplier'],
            data['preparation_date'],
            data['notes'],
            data['solvents'],
            data['solubility'],
            data['light_sensitive'],
            data['preparation_time'],
            data['expiration_time'],
            data['sterility'],
            data['lot_number'],
            data['product_number'],
            data.get('storage_section'),
            data.get('storage_row'),
            data.get('storage_column'),
            data.get('aliquot_volume')
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def update_record(self, record_id, data):
        """Update an existing record"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE drugs SET
                drug_name = ?,
                stock_concentration = ?,
                stock_unit = ?,
                storage_temp = ?,
                supplier = ?,
                preparation_date = ?,
                notes = ?,
                solvents = ?,
                solubility = ?,
                light_sensitive = ?,
                preparation_time = ?,
                expiration_time = ?,
                sterility = ?,
                lot_number = ?,
                product_number = ?,
                storage_section = ?,
                storage_row = ?,
                storage_column = ?,
                aliquot_volume = ?
            WHERE id = ?
        ''', (
            data['drug_name'],
            data['stock_concentration'],
            data['stock_unit'],
            data['storage_temp'],
            data['supplier'],
            data['preparation_date'],
            data['notes'],
            data['solvents'],
            data['solubility'],
            data['light_sensitive'],
            data['preparation_time'],
            data['expiration_time'],
            data['sterility'],
            data['lot_number'],
            data['product_number'],
            data.get('storage_section'),
            data.get('storage_row'),
            data.get('storage_column'),
            data.get('aliquot_volume'),
            record_id
        ))

        conn.commit()
        conn.close()

    def delete_record(self, record_id):
        """Delete a record from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM drugs WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()

    def search_records(self, search_term, filter_temp=None):
        """Search records by name or other fields"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT * FROM drugs
            WHERE (drug_name LIKE ? OR supplier LIKE ? OR notes LIKE ?)
        '''
        params = [f'%{search_term}%', f'%{search_term}%', f'%{search_term}%']

        if filter_temp:
            query += ' AND storage_temp = ?'
            params.append(filter_temp)

        query += ' ORDER BY id DESC'

        cursor.execute(query, params)
        records = cursor.fetchall()
        conn.close()
        return records

    def get_records_by_location(self, temp_key, section, row, col):
        """Get all records at a specific storage location"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM drugs
            WHERE storage_temp = ?
            AND storage_section = ?
            AND storage_row = ?
            AND storage_column = ?
        ''', (temp_key, section, row, col))

        records = cursor.fetchall()
        conn.close()
        return records

    def get_fridge_config(self, temp_key):
        """Get fridge configuration for a specific temperature"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fridge_config WHERE temp_key = ?', (temp_key,))
        config = cursor.fetchone()
        conn.close()
        return config

    def get_all_fridge_configs(self):
        """Get all fridge configurations"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fridge_config ORDER BY temp_key')
        configs = cursor.fetchall()
        conn.close()
        return configs

    def update_fridge_config(self, temp_key, body_rows, body_cols, door_rows, door_cols):
        """Update fridge configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE fridge_config
            SET body_rows = ?, body_columns = ?, door_rows = ?, door_columns = ?
            WHERE temp_key = ?
        ''', (body_rows, body_cols, door_rows, door_cols, temp_key))

        conn.commit()
        conn.close()

    def get_storage_grid_data(self, temp_key):
        """Get grid data for a specific fridge including item counts per cell"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get all records for this temperature
        cursor.execute('''
            SELECT storage_section, storage_row, storage_column, COUNT(*) as count
            FROM drugs
            WHERE storage_temp = ?
            AND storage_section IS NOT NULL
            AND storage_row IS NOT NULL
            AND storage_column IS NOT NULL
            GROUP BY storage_section, storage_row, storage_column
        ''', (temp_key,))

        grid_data = {}
        for row in cursor.fetchall():
            key = f"{row['storage_section']}-{row['storage_row']}-{row['storage_column']}"
            grid_data[key] = row['count']

        conn.close()
        return grid_data

    def export_to_csv(self):
        """Export all records to CSV format"""
        records = self.get_all_records()

        csv_lines = []
        # Header
        csv_lines.append(','.join([
            'ID', 'Drug Name', 'Stock Concentration', 'Unit', 'Storage Temperature',
            'Supplier', 'Preparation Date', 'Notes', 'Solvents', 'Solubility',
            'Light Sensitive', 'Preparation Time', 'Expiration Time', 'Sterility',
            'Lot Number', 'Product Number', 'Storage Section', 'Storage Row', 'Storage Column',
            'Aliquot Volume'
        ]))

        # Data rows
        for record in records:
            csv_lines.append(','.join([
                str(record['id']),
                f'"{record["drug_name"]}"',
                str(record['stock_concentration'] or ''),
                f'"{record["stock_unit"] or ""}"',
                f'"{record["storage_temp"] or ""}"',
                f'"{record["supplier"] or ""}"',
                f'"{record["preparation_date"] or ""}"',
                f'"{record["notes"] or ""}"',
                f'"{record["solvents"] or ""}"',
                f'"{record["solubility"] or ""}"',
                f'"{record["light_sensitive"] or ""}"',
                f'"{record["preparation_time"] or ""}"',
                f'"{record["expiration_time"] or ""}"',
                f'"{record["sterility"] or ""}"',
                f'"{record["lot_number"] or ""}"',
                f'"{record["product_number"] or ""}"',
                f'"{record["storage_section"] or ""}"',
                str(record['storage_row'] or ''),
                str(record['storage_column'] or ''),
                f'"{record["aliquot_volume"] or ""}"'
            ]))

        return '\n'.join(csv_lines)

    def import_from_csv(self, csv_content, skip_duplicates=True):
        """Import records from CSV content with transaction support.

        All inserts are wrapped in a transaction - if any critical error occurs,
        the entire import is rolled back to maintain database consistency.
        """
        import csv
        from io import StringIO

        results = {
            'success': 0,
            'skipped': 0,
            'errors': []
        }

        # Parse CSV
        csv_reader = csv.DictReader(StringIO(csv_content))

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Begin explicit transaction
            cursor.execute('BEGIN TRANSACTION')

            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is header)
                try:
                    # Clean and prepare data
                    drug_name = row.get('Drug Name', '').strip()

                    if not drug_name:
                        results['errors'].append(f"Row {row_num}: Missing drug name")
                        continue

                    # Check for duplicates if requested
                    if skip_duplicates:
                        cursor.execute('SELECT COUNT(*) FROM drugs WHERE drug_name = ?', (drug_name,))
                        if cursor.fetchone()[0] > 0:
                            results['skipped'] += 1
                            continue

                    # Prepare data
                    stock_concentration = row.get('Stock Concentration', '').strip()
                    if stock_concentration:
                        try:
                            stock_concentration = float(stock_concentration)
                        except ValueError:
                            stock_concentration = None
                    else:
                        stock_concentration = None

                    storage_row = row.get('Storage Row', '').strip()
                    if storage_row:
                        try:
                            storage_row = int(storage_row)
                        except ValueError:
                            storage_row = None
                    else:
                        storage_row = None

                    storage_column = row.get('Storage Column', '').strip()
                    if storage_column:
                        try:
                            storage_column = int(storage_column)
                        except ValueError:
                            storage_column = None
                    else:
                        storage_column = None

                    # Insert record
                    cursor.execute('''
                        INSERT INTO drugs (
                            drug_name, stock_concentration, stock_unit, storage_temp,
                            supplier, preparation_date, notes, solvents, solubility,
                            light_sensitive, preparation_time, expiration_time, sterility,
                            lot_number, product_number, storage_section, storage_row, storage_column,
                            aliquot_volume
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        drug_name,
                        stock_concentration,
                        row.get('Unit', '').strip() or None,
                        row.get('Storage Temperature', '').strip() or None,
                        row.get('Supplier', '').strip() or None,
                        row.get('Preparation Date', '').strip() or None,
                        row.get('Notes', '').strip() or None,
                        row.get('Solvents', '').strip() or None,
                        row.get('Solubility', '').strip() or None,
                        row.get('Light Sensitive', '').strip() or None,
                        row.get('Preparation Time', '').strip() or None,
                        row.get('Expiration Time', '').strip() or None,
                        row.get('Sterility', '').strip() or None,
                        row.get('Lot Number', '').strip() or None,
                        row.get('Product Number', '').strip() or None,
                        row.get('Storage Section', '').strip() or None,
                        storage_row,
                        storage_column,
                        row.get('Aliquot Volume', '').strip() or None
                    ))

                    results['success'] += 1

                except Exception as e:
                    results['errors'].append(f"Row {row_num}: {str(e)}")

            # Commit the transaction if we got here successfully
            conn.commit()

        except Exception as e:
            # Rollback on any critical error
            conn.rollback()
            results['errors'].append(f"Critical error - import rolled back: {str(e)}")
            results['success'] = 0  # Reset success count since we rolled back

        finally:
            conn.close()

        return results

    # ========== VISUAL FRIDGE LAYOUT METHODS ==========

    def create_or_update_layout(self, temp_key, section, photo_filename):
        """Create or update a fridge layout with photo"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO fridge_layouts (temp_key, section, photo_filename, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(temp_key, section)
            DO UPDATE SET photo_filename = ?, updated_at = CURRENT_TIMESTAMP
        ''', (temp_key, section, photo_filename, photo_filename))

        layout_id = cursor.lastrowid or cursor.execute(
            'SELECT id FROM fridge_layouts WHERE temp_key = ? AND section = ?',
            (temp_key, section)
        ).fetchone()[0]

        conn.commit()
        conn.close()
        return layout_id

    def get_layout(self, temp_key, section):
        """Get fridge layout for specific temperature and section"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM fridge_layouts
            WHERE temp_key = ? AND section = ?
        ''', (temp_key, section))
        layout = cursor.fetchone()
        conn.close()
        return layout

    def get_all_layouts(self):
        """Get all fridge layouts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fridge_layouts ORDER BY temp_key, section')
        layouts = cursor.fetchall()
        conn.close()
        return layouts

    def create_region(self, layout_id, region_name, x, y, width, height):
        """Create a new region on a fridge layout"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO fridge_regions (layout_id, region_name, x, y, width, height)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (layout_id, region_name, x, y, width, height))

        region_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return region_id

    def update_region(self, region_id, region_name, x, y, width, height):
        """Update an existing region"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE fridge_regions
            SET region_name = ?, x = ?, y = ?, width = ?, height = ?
            WHERE id = ?
        ''', (region_name, x, y, width, height, region_id))

        conn.commit()
        conn.close()

    def delete_region(self, region_id):
        """Delete a region"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM fridge_regions WHERE id = ?', (region_id,))
        conn.commit()
        conn.close()

    def get_regions_for_layout(self, layout_id):
        """Get all regions for a specific layout"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM fridge_regions
            WHERE layout_id = ?
            ORDER BY region_name
        ''', (layout_id,))
        regions = cursor.fetchall()
        conn.close()
        return regions

    def get_region_by_id(self, region_id):
        """Get a specific region by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fridge_regions WHERE id = ?', (region_id,))
        region = cursor.fetchone()
        conn.close()
        return region

    def get_items_in_region(self, region_id):
        """Get all items stored in a specific region"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM drugs
            WHERE fridge_region_id = ?
            ORDER BY drug_name
        ''', (region_id,))
        items = cursor.fetchall()
        conn.close()
        return items

    def assign_item_to_region(self, drug_id, region_id):
        """Assign an inventory item to a visual region"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE drugs
            SET fridge_region_id = ?
            WHERE id = ?
        ''', (region_id, drug_id))
        conn.commit()
        conn.close()

    def get_region_occupancy(self, layout_id):
        """Get item counts for all regions in a layout"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT fr.id, fr.region_name, COUNT(d.id) as item_count
            FROM fridge_regions fr
            LEFT JOIN drugs d ON d.fridge_region_id = fr.id
            WHERE fr.layout_id = ?
            GROUP BY fr.id, fr.region_name
            ORDER BY fr.region_name
        ''', (layout_id,))
        occupancy = cursor.fetchall()
        conn.close()
        return occupancy

    # ========== SCHEMATIC LAYOUT METHODS ==========

    def create_schematic_layout(self, temp_key, section, layout_name=None, reference_photo=None):
        """Create a new schematic layout"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO fridge_schematic_layouts (temp_key, section, layout_name, reference_photo, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(temp_key, section)
            DO UPDATE SET layout_name = ?, reference_photo = ?, updated_at = CURRENT_TIMESTAMP
        ''', (temp_key, section, layout_name, reference_photo, layout_name, reference_photo))

        layout_id = cursor.lastrowid or cursor.execute(
            'SELECT id FROM fridge_schematic_layouts WHERE temp_key = ? AND section = ?',
            (temp_key, section)
        ).fetchone()[0]

        conn.commit()
        conn.close()
        return layout_id

    def get_schematic_layout(self, temp_key, section):
        """Get schematic layout for specific temperature and section"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM fridge_schematic_layouts
            WHERE temp_key = ? AND section = ?
        ''', (temp_key, section))
        layout = cursor.fetchone()
        conn.close()
        return layout

    def get_all_schematic_layouts(self):
        """Get all schematic layouts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fridge_schematic_layouts ORDER BY temp_key, section')
        layouts = cursor.fetchall()
        conn.close()
        return layouts

    def delete_schematic_layout(self, layout_id):
        """Delete a schematic layout and all its zones"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM fridge_schematic_zones WHERE layout_id = ?', (layout_id,))
        cursor.execute('DELETE FROM fridge_schematic_layouts WHERE id = ?', (layout_id,))
        conn.commit()
        conn.close()

    def add_schematic_zone(self, layout_id, zone_name, row_index, col_index, col_span=1, row_span=1, color='#e3f2fd'):
        """Add a zone to a schematic layout"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO fridge_schematic_zones (layout_id, zone_name, row_index, col_index, col_span, row_span, color)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (layout_id, zone_name, row_index, col_index, col_span, row_span, color))

        zone_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return zone_id

    def update_schematic_zone(self, zone_id, zone_name, row_index, col_index, col_span=1, row_span=1, color='#e3f2fd'):
        """Update a schematic zone"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE fridge_schematic_zones
            SET zone_name = ?, row_index = ?, col_index = ?, col_span = ?, row_span = ?, color = ?
            WHERE id = ?
        ''', (zone_name, row_index, col_index, col_span, row_span, color, zone_id))

        conn.commit()
        conn.close()

    def delete_schematic_zone(self, zone_id):
        """Delete a schematic zone"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM fridge_schematic_zones WHERE id = ?', (zone_id,))
        conn.commit()
        conn.close()

    def get_schematic_zones(self, layout_id):
        """Get all zones for a schematic layout"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM fridge_schematic_zones
            WHERE layout_id = ?
            ORDER BY row_index, col_index
        ''', (layout_id,))
        zones = cursor.fetchall()
        conn.close()
        return zones

    def get_schematic_zone_by_id(self, zone_id):
        """Get a specific schematic zone"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM fridge_schematic_zones WHERE id = ?', (zone_id,))
        zone = cursor.fetchone()
        conn.close()
        return zone

    def get_items_in_zone(self, zone_id):
        """Get all items stored in a schematic zone"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM drugs
            WHERE fridge_region_id = ?
            ORDER BY drug_name
        ''', (zone_id,))
        items = cursor.fetchall()
        conn.close()
        return items

    def assign_item_to_zone(self, drug_id, zone_id):
        """Assign an inventory item to a schematic zone"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE drugs
            SET fridge_region_id = ?
            WHERE id = ?
        ''', (zone_id, drug_id))
        conn.commit()
        conn.close()

    def get_zone_occupancy(self, layout_id):
        """Get item counts for all zones in a schematic layout"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT z.id, z.zone_name, z.row_index, z.col_index, z.color, COUNT(d.id) as item_count
            FROM fridge_schematic_zones z
            LEFT JOIN drugs d ON d.fridge_region_id = z.id
            WHERE z.layout_id = ?
            GROUP BY z.id, z.zone_name, z.row_index, z.col_index, z.color
            ORDER BY z.row_index, z.col_index
        ''', (layout_id,))
        occupancy = cursor.fetchall()
        conn.close()
        return occupancy

    def clear_schematic_zones(self, layout_id):
        """Delete all zones from a schematic layout"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM fridge_schematic_zones WHERE layout_id = ?', (layout_id,))
        conn.commit()
        conn.close()

    # ========== ANTIBODY METHODS ==========

    def get_all_primary_antibodies(self):
        """Get all primary antibodies"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM primary_antibodies ORDER BY name')
        antibodies = cursor.fetchall()
        conn.close()
        return antibodies

    def get_primary_antibody_by_id(self, ab_id):
        """Get a single primary antibody by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM primary_antibodies WHERE id = ?', (ab_id,))
        antibody = cursor.fetchone()
        conn.close()
        return antibody

    def add_primary_antibody(self, data):
        """Add a new primary antibody"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO primary_antibodies (
                name, target_protein, host_species, clonality, isotype, clone_number,
                supplier, catalog_number, lot_number, applications, fixation_compatibility,
                dilution_if, dilution_wb, dilution_ihc, storage_temp, stock_concentration,
                aliquot_volume, validated, notes, fridge_region_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            data.get('target_protein'),
            data.get('host_species'),
            data.get('clonality'),
            data.get('isotype'),
            data.get('clone_number'),
            data.get('supplier'),
            data.get('catalog_number'),
            data.get('lot_number'),
            data.get('applications'),
            data.get('fixation_compatibility'),
            data.get('dilution_if'),
            data.get('dilution_wb'),
            data.get('dilution_ihc'),
            data.get('storage_temp'),
            data.get('stock_concentration'),
            data.get('aliquot_volume'),
            data.get('validated'),
            data.get('notes'),
            data.get('fridge_region_id')
        ))

        ab_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ab_id

    def update_primary_antibody(self, ab_id, data):
        """Update a primary antibody"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE primary_antibodies SET
                name = ?, target_protein = ?, host_species = ?, clonality = ?,
                isotype = ?, clone_number = ?, supplier = ?, catalog_number = ?,
                lot_number = ?, applications = ?, fixation_compatibility = ?,
                dilution_if = ?, dilution_wb = ?, dilution_ihc = ?, storage_temp = ?,
                stock_concentration = ?, aliquot_volume = ?, validated = ?, notes = ?,
                fridge_region_id = ?
            WHERE id = ?
        ''', (
            data.get('name'),
            data.get('target_protein'),
            data.get('host_species'),
            data.get('clonality'),
            data.get('isotype'),
            data.get('clone_number'),
            data.get('supplier'),
            data.get('catalog_number'),
            data.get('lot_number'),
            data.get('applications'),
            data.get('fixation_compatibility'),
            data.get('dilution_if'),
            data.get('dilution_wb'),
            data.get('dilution_ihc'),
            data.get('storage_temp'),
            data.get('stock_concentration'),
            data.get('aliquot_volume'),
            data.get('validated'),
            data.get('notes'),
            data.get('fridge_region_id'),
            ab_id
        ))

        conn.commit()
        conn.close()

    def delete_primary_antibody(self, ab_id):
        """Delete a primary antibody"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM primary_antibodies WHERE id = ?', (ab_id,))
        conn.commit()
        conn.close()

    def get_all_secondary_antibodies(self):
        """Get all secondary antibodies"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM secondary_antibodies ORDER BY name')
        antibodies = cursor.fetchall()
        conn.close()
        return antibodies

    def get_secondary_antibody_by_id(self, ab_id):
        """Get a single secondary antibody by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM secondary_antibodies WHERE id = ?', (ab_id,))
        antibody = cursor.fetchone()
        conn.close()
        return antibody

    def add_secondary_antibody(self, data):
        """Add a new secondary antibody"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO secondary_antibodies (
                name, target_species, target_isotype, host_species, format, conjugate,
                fluorophore_excitation, fluorophore_emission, cross_adsorbed,
                cross_adsorbed_against, supplier, catalog_number, lot_number,
                applications, dilution_if, dilution_wb, dilution_ihc, storage_temp,
                stock_concentration, aliquot_volume, notes, fridge_region_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            data.get('target_species'),
            data.get('target_isotype'),
            data.get('host_species'),
            data.get('format'),
            data.get('conjugate'),
            data.get('fluorophore_excitation'),
            data.get('fluorophore_emission'),
            data.get('cross_adsorbed'),
            data.get('cross_adsorbed_against'),
            data.get('supplier'),
            data.get('catalog_number'),
            data.get('lot_number'),
            data.get('applications'),
            data.get('dilution_if'),
            data.get('dilution_wb'),
            data.get('dilution_ihc'),
            data.get('storage_temp'),
            data.get('stock_concentration'),
            data.get('aliquot_volume'),
            data.get('notes'),
            data.get('fridge_region_id')
        ))

        ab_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ab_id

    def update_secondary_antibody(self, ab_id, data):
        """Update a secondary antibody"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE secondary_antibodies SET
                name = ?, target_species = ?, target_isotype = ?, host_species = ?,
                format = ?, conjugate = ?, fluorophore_excitation = ?,
                fluorophore_emission = ?, cross_adsorbed = ?, cross_adsorbed_against = ?,
                supplier = ?, catalog_number = ?, lot_number = ?, applications = ?,
                dilution_if = ?, dilution_wb = ?, dilution_ihc = ?, storage_temp = ?,
                stock_concentration = ?, aliquot_volume = ?, notes = ?, fridge_region_id = ?
            WHERE id = ?
        ''', (
            data.get('name'),
            data.get('target_species'),
            data.get('target_isotype'),
            data.get('host_species'),
            data.get('format'),
            data.get('conjugate'),
            data.get('fluorophore_excitation'),
            data.get('fluorophore_emission'),
            data.get('cross_adsorbed'),
            data.get('cross_adsorbed_against'),
            data.get('supplier'),
            data.get('catalog_number'),
            data.get('lot_number'),
            data.get('applications'),
            data.get('dilution_if'),
            data.get('dilution_wb'),
            data.get('dilution_ihc'),
            data.get('storage_temp'),
            data.get('stock_concentration'),
            data.get('aliquot_volume'),
            data.get('notes'),
            data.get('fridge_region_id'),
            ab_id
        ))

        conn.commit()
        conn.close()

    def delete_secondary_antibody(self, ab_id):
        """Delete a secondary antibody"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM secondary_antibodies WHERE id = ?', (ab_id,))
        conn.commit()
        conn.close()

    def find_matching_secondaries(self, primary_id):
        """Find secondary antibodies compatible with a given primary antibody"""
        primary = self.get_primary_antibody_by_id(primary_id)
        if not primary:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get the primary's host species and isotype
        host_species = primary['host_species']
        isotype = primary['isotype']
        clonality = primary['clonality']

        # Find secondaries that target the primary's host species
        query = '''
            SELECT * FROM secondary_antibodies
            WHERE LOWER(target_species) = LOWER(?)
        '''
        params = [host_species]

        # If monoclonal and specific isotype, prefer matching isotype or H+L
        # But still return all that match species
        cursor.execute(query, params)
        secondaries = cursor.fetchall()
        conn.close()

        # Score and sort the matches
        scored = []
        for sec in secondaries:
            score = 0
            reasons = []

            # Check isotype match
            target_isotype = (sec['target_isotype'] or '').lower()
            primary_isotype = (isotype or '').lower()

            if 'h+l' in target_isotype or 'h&l' in target_isotype:
                score += 2
                reasons.append("H+L (broad)")
            elif primary_isotype and primary_isotype in target_isotype:
                score += 3
                reasons.append(f"Isotype match ({isotype})")
            elif clonality == 'Polyclonal' and 'igg' in target_isotype:
                score += 2
                reasons.append("IgG for polyclonal")

            # Bonus for cross-adsorbed
            if sec['cross_adsorbed'] == 'Yes':
                score += 1
                reasons.append("Cross-adsorbed")

            scored.append({
                'antibody': dict(sec),
                'score': score,
                'reasons': reasons
            })

        # Sort by score (descending)
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored

    # ========== SETTINGS METHODS ==========

    def get_setting(self, key):
        """Get a setting value by key"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result['value'] if result else None

    def set_setting(self, key, value):
        """Set a setting value"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        ''', (key, value))
        conn.commit()
        conn.close()

    def get_all_settings(self):
        """Get all settings as a dictionary"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM settings')
        results = cursor.fetchall()
        conn.close()
        return {row['key']: row['value'] for row in results}
