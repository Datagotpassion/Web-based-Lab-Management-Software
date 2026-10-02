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
                aliquot_volume TEXT,
                container_id INTEGER,
                product_url TEXT
            )
        ''')

        # Columns added after the original schema. Location lives in
        # container_id, pointing into the storage_containers tree; the old
        # storage_section / storage_row / storage_column grid and the
        # fridge_region_id zone link were dropped by migrate_cleanup.py.
        existing_columns = [col[1] for col in cursor.execute("PRAGMA table_info(drugs)").fetchall()]
        new_columns = [
            ('aliquot_volume', 'TEXT'),  # e.g. "50 µL", "1 mL"
            ('container_id', 'INTEGER'),  # location in the storage container tree
            ('product_url', 'TEXT')  # supplier page the details were taken from
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cursor.execute(f'ALTER TABLE drugs ADD COLUMN {col_name} {col_type}')

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
                container_id INTEGER,
                is_conjugated INTEGER DEFAULT 0,
                fluorophore TEXT,
                fluorophore_excitation TEXT,
                fluorophore_emission TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration: Add conjugation columns to primary_antibodies if missing
        cursor.execute("PRAGMA table_info(primary_antibodies)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_conjugated' not in columns:
            cursor.execute('ALTER TABLE primary_antibodies ADD COLUMN is_conjugated INTEGER DEFAULT 0')
        if 'fluorophore' not in columns:
            cursor.execute('ALTER TABLE primary_antibodies ADD COLUMN fluorophore TEXT')
        if 'fluorophore_excitation' not in columns:
            cursor.execute('ALTER TABLE primary_antibodies ADD COLUMN fluorophore_excitation TEXT')
        if 'fluorophore_emission' not in columns:
            cursor.execute('ALTER TABLE primary_antibodies ADD COLUMN fluorophore_emission TEXT')

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
                container_id INTEGER,
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
                lot_number, product_number, aliquot_volume, container_id,
                product_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get('aliquot_volume'),
            # Location is a node in the storage_containers tree.
            data.get('container_id'),
            data.get('product_url')
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
                aliquot_volume = ?,
                container_id = ?,
                product_url = ?
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
            data.get('aliquot_volume'),
            data.get('container_id'),
            data.get('product_url'),
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

    def container_paths(self):
        """container id -> 'Unit > Section > Shelf > ...', for CSV export.

        Built here with a recursive CTE rather than via StorageTree so the
        export stays a single query and database.py keeps no import of it.
        """
        conn = self.get_connection()
        try:
            rows = conn.execute('''
                WITH RECURSIVE up(start_id, id, label, parent_id, unit_id, depth) AS (
                    SELECT id, id, label, parent_id, unit_id, 0
                      FROM storage_containers
                    UNION ALL
                    SELECT up.start_id, p.id, p.label, p.parent_id, p.unit_id,
                           up.depth + 1
                      FROM storage_containers p JOIN up ON up.parent_id = p.id
                )
                SELECT up.start_id, u.name AS unit, up.label, up.depth
                  FROM up JOIN storage_units u ON u.id = up.unit_id
                 ORDER BY up.start_id, up.depth DESC
            ''').fetchall()
        except sqlite3.OperationalError:
            # Storage tables not created yet (very fresh database).
            return {}
        finally:
            conn.close()

        paths = {}
        for r in rows:
            entry = paths.setdefault(r['start_id'], [r['unit']])
            entry.append(r['label'])
        return {k: ' > '.join(v) for k, v in paths.items()}

    def export_to_csv(self):
        """Export all records to CSV format"""
        records = self.get_all_records()
        paths = self.container_paths()

        csv_lines = []
        # Header
        csv_lines.append(','.join([
            'ID', 'Drug Name', 'Stock Concentration', 'Unit', 'Storage Temperature',
            'Supplier', 'Preparation Date', 'Notes', 'Solvents', 'Solubility',
            'Light Sensitive', 'Preparation Time', 'Expiration Time', 'Sterility',
            'Lot Number', 'Product Number', 'Location', 'Aliquot Volume'
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
                f'"{paths.get(record["container_id"], "")}"',
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

        # Reverse of container_paths, so an exported "Location" resolves back.
        path_to_id = {v: k for k, v in self.container_paths().items()}

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

                    # Match the exported "Location" path back to a container, so
                    # an export/import round trip keeps locations. An unknown or
                    # blank path simply leaves the item unplaced rather than
                    # failing the import.
                    location = row.get('Location', '').strip()
                    container_id = path_to_id.get(location) if location else None

                    # Insert record
                    cursor.execute('''
                        INSERT INTO drugs (
                            drug_name, stock_concentration, stock_unit, storage_temp,
                            supplier, preparation_date, notes, solvents, solubility,
                            light_sensitive, preparation_time, expiration_time, sterility,
                            lot_number, product_number, container_id,
                            aliquot_volume
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        container_id,
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
                aliquot_volume, validated, notes, container_id,
                is_conjugated, fluorophore, fluorophore_excitation, fluorophore_emission
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get('container_id'),
            1 if data.get('is_conjugated') else 0,
            data.get('fluorophore'),
            data.get('fluorophore_excitation'),
            data.get('fluorophore_emission')
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
                container_id = ?, is_conjugated = ?, fluorophore = ?,
                fluorophore_excitation = ?, fluorophore_emission = ?
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
            data.get('container_id'),
            1 if data.get('is_conjugated') else 0,
            data.get('fluorophore'),
            data.get('fluorophore_excitation'),
            data.get('fluorophore_emission'),
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
                stock_concentration, aliquot_volume, notes, container_id
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
            data.get('container_id')
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
                stock_concentration = ?, aliquot_volume = ?, notes = ?, container_id = ?
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
            data.get('container_id'),
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

    # ========== FRIDGE MANAGEMENT METHODS ==========
