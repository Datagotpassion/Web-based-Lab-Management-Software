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
            ('storage_column', 'INTEGER')
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cursor.execute(f'ALTER TABLE drugs ADD COLUMN {col_name} {col_type}')

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
                lot_number, product_number, storage_section, storage_row, storage_column
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
            data.get('storage_section'),
            data.get('storage_row'),
            data.get('storage_column')
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
                storage_column = ?
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
            'Lot Number', 'Product Number', 'Storage Section', 'Storage Row', 'Storage Column'
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
                str(record['storage_column'] or '')
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
                            lot_number, product_number, storage_section, storage_row, storage_column
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        storage_column
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
