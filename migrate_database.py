"""
Database Migration Script
Migrates the old desktop database schema to the new web application schema
"""

import sqlite3
import shutil
from datetime import datetime

# Backup the database first
backup_name = f'lab_management_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
print(f"Creating backup: {backup_name}")
shutil.copy('lab_management.db', backup_name)
print("OK - Backup created successfully")

# Connect to database
conn = sqlite3.connect('lab_management.db')
cursor = conn.cursor()

print("\nChecking current database schema...")
columns = cursor.execute('PRAGMA table_info(drugs)').fetchall()
existing_columns = {col[1]: col[2] for col in columns}

print(f"Found {len(existing_columns)} columns in drugs table")

# Define column mappings (old_name -> new_name)
column_mappings = {
    'concentration': 'stock_concentration',
    'conc_unit': 'stock_unit'
}

# Columns to add if missing
new_columns = {
    'supplier': 'TEXT',
    'notes': 'TEXT'
}

# Step 1: Add new columns if they don't exist
print("\n--- Adding missing columns ---")
for col_name, col_type in new_columns.items():
    if col_name not in existing_columns:
        try:
            cursor.execute(f'ALTER TABLE drugs ADD COLUMN {col_name} {col_type}')
            print(f"OK - Added column: {col_name}")
        except Exception as e:
            print(f"ERROR - Error adding {col_name}: {e}")

# Step 2: Create new table with correct schema
print("\n--- Creating new table with correct schema ---")
cursor.execute('''
    CREATE TABLE IF NOT EXISTS drugs_new (
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
        storage_column INTEGER,
        aliquot_volume TEXT,
        preparation_method TEXT,
        date_created TEXT,
        category TEXT
    )
''')
print("OK - Created new table schema")

# Step 3: Copy data from old table to new table with column mapping
print("\n--- Migrating data ---")
cursor.execute('SELECT * FROM drugs')
old_records = cursor.fetchall()

# Get column names from old table
old_column_names = [col[1] for col in columns]

migrated_count = 0
for record in old_records:
    # Create a dictionary of old data
    old_data = dict(zip(old_column_names, record))

    # Map to new column names
    new_data = {
        'id': old_data.get('id'),
        'drug_name': old_data.get('drug_name'),
        'stock_concentration': old_data.get('concentration'),  # Map concentration -> stock_concentration
        'stock_unit': old_data.get('conc_unit'),  # Map conc_unit -> stock_unit
        'storage_temp': old_data.get('storage_temp'),
        'supplier': old_data.get('supplier'),
        'preparation_date': old_data.get('date_created'),  # Map date_created -> preparation_date
        'notes': old_data.get('notes'),
        'solvents': old_data.get('solvents'),
        'solubility': old_data.get('solubility'),
        'light_sensitive': old_data.get('light_sensitive'),
        'preparation_time': old_data.get('preparation_time'),
        'expiration_time': old_data.get('expiration_time'),
        'sterility': old_data.get('sterility'),
        'lot_number': old_data.get('lot_number'),
        'product_number': old_data.get('product_number'),
        'storage_section': old_data.get('storage_section'),
        'storage_row': old_data.get('storage_row'),
        'storage_column': old_data.get('storage_column'),
        'aliquot_volume': old_data.get('aliquot_volume'),
        'preparation_method': old_data.get('preparation_method'),
        'date_created': old_data.get('date_created'),
        'category': old_data.get('category')
    }

    # Convert concentration to REAL if it's a string
    if new_data['stock_concentration']:
        try:
            new_data['stock_concentration'] = float(new_data['stock_concentration'])
        except (ValueError, TypeError):
            new_data['stock_concentration'] = None

    # Insert into new table
    cursor.execute('''
        INSERT INTO drugs_new (
            id, drug_name, stock_concentration, stock_unit, storage_temp,
            supplier, preparation_date, notes, solvents, solubility,
            light_sensitive, preparation_time, expiration_time, sterility,
            lot_number, product_number, storage_section, storage_row, storage_column,
            aliquot_volume, preparation_method, date_created, category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        new_data['id'],
        new_data['drug_name'],
        new_data['stock_concentration'],
        new_data['stock_unit'],
        new_data['storage_temp'],
        new_data['supplier'],
        new_data['preparation_date'],
        new_data['notes'],
        new_data['solvents'],
        new_data['solubility'],
        new_data['light_sensitive'],
        new_data['preparation_time'],
        new_data['expiration_time'],
        new_data['sterility'],
        new_data['lot_number'],
        new_data['product_number'],
        new_data['storage_section'],
        new_data['storage_row'],
        new_data['storage_column'],
        new_data['aliquot_volume'],
        new_data['preparation_method'],
        new_data['date_created'],
        new_data['category']
    ))
    migrated_count += 1

print(f"OK - Migrated {migrated_count} records")

# Step 4: Drop old table and rename new table
print("\n--- Replacing old table with new schema ---")
cursor.execute('DROP TABLE drugs')
cursor.execute('ALTER TABLE drugs_new RENAME TO drugs')
print("OK - Table replacement complete")

# Step 5: Verify migration
cursor.execute('SELECT COUNT(*) FROM drugs')
final_count = cursor.fetchone()[0]
print(f"\nOK - Verification: {final_count} records in new table")

# Commit changes
conn.commit()
conn.close()

print("\n" + "="*80)
print("MIGRATION COMPLETED SUCCESSFULLY!")
print("="*80)
print(f"\nOriginal database backed up to: {backup_name}")
print("Database schema updated to match web application requirements")
print("\nYou can now run the Flask application:")
print("  python app.py")
print("\n" + "="*80)
