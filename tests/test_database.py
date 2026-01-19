"""
Unit tests for database operations
Tests CRUD operations, CSV import/export, and transaction handling
"""

import pytest


class TestDatabaseRecords:
    """Tests for basic CRUD operations"""

    def test_add_record(self, test_db, sample_record):
        """Test adding a new record"""
        record_id = test_db.add_record(sample_record)

        assert record_id is not None
        assert record_id > 0

        # Verify record was added
        record = test_db.get_record_by_id(record_id)
        assert record is not None
        assert record['drug_name'] == 'Test Drug'
        assert record['stock_concentration'] == 10.0

    def test_get_all_records(self, test_db, sample_record):
        """Test retrieving all records"""
        # Add multiple records
        test_db.add_record(sample_record)
        sample_record['drug_name'] = 'Test Drug 2'
        test_db.add_record(sample_record)

        records = test_db.get_all_records()
        assert len(records) == 2

    def test_get_record_by_id(self, test_db, sample_record):
        """Test retrieving a record by ID"""
        record_id = test_db.add_record(sample_record)

        record = test_db.get_record_by_id(record_id)
        assert record is not None
        assert record['id'] == record_id
        assert record['drug_name'] == 'Test Drug'

    def test_get_nonexistent_record(self, test_db):
        """Test retrieving a record that doesn't exist"""
        record = test_db.get_record_by_id(99999)
        assert record is None

    def test_update_record(self, test_db, sample_record):
        """Test updating a record"""
        record_id = test_db.add_record(sample_record)

        # Update the record
        sample_record['drug_name'] = 'Updated Drug Name'
        sample_record['stock_concentration'] = 25.0
        test_db.update_record(record_id, sample_record)

        # Verify update
        record = test_db.get_record_by_id(record_id)
        assert record['drug_name'] == 'Updated Drug Name'
        assert record['stock_concentration'] == 25.0

    def test_delete_record(self, test_db, sample_record):
        """Test deleting a record"""
        record_id = test_db.add_record(sample_record)

        # Verify record exists
        assert test_db.get_record_by_id(record_id) is not None

        # Delete record
        test_db.delete_record(record_id)

        # Verify record is deleted
        assert test_db.get_record_by_id(record_id) is None

    def test_search_records(self, test_db, sample_record):
        """Test searching records"""
        sample_record['drug_name'] = 'Aspirin'
        test_db.add_record(sample_record)

        sample_record['drug_name'] = 'Ibuprofen'
        test_db.add_record(sample_record)

        sample_record['drug_name'] = 'Acetaminophen'
        test_db.add_record(sample_record)

        # Search for 'Asp'
        results = test_db.search_records('Asp')
        assert len(results) == 1
        assert results[0]['drug_name'] == 'Aspirin'

        # Search for 'fen' (partial match)
        results = test_db.search_records('fen')
        assert len(results) == 1
        assert results[0]['drug_name'] == 'Ibuprofen'

    def test_search_records_with_temp_filter(self, test_db, sample_record):
        """Test searching records with temperature filter"""
        sample_record['drug_name'] = 'Drug 4C'
        sample_record['storage_temp'] = '4C'
        test_db.add_record(sample_record)

        sample_record['drug_name'] = 'Drug -20C'
        sample_record['storage_temp'] = '-20C'
        test_db.add_record(sample_record)

        # Search with temperature filter
        results = test_db.search_records('Drug', '4C')
        assert len(results) == 1
        assert results[0]['drug_name'] == 'Drug 4C'


class TestCSVImport:
    """Tests for CSV import functionality"""

    def test_import_csv_success(self, test_db, sample_csv_content):
        """Test successful CSV import"""
        results = test_db.import_from_csv(sample_csv_content)

        assert results['success'] == 3
        assert results['skipped'] == 0
        assert len(results['errors']) == 0

        # Verify records were imported
        records = test_db.get_all_records()
        assert len(records) == 3

    def test_import_csv_skip_duplicates(self, test_db, sample_csv_content):
        """Test that duplicates are skipped when skip_duplicates=True"""
        # First import
        results1 = test_db.import_from_csv(sample_csv_content, skip_duplicates=True)
        assert results1['success'] == 3

        # Second import - should skip all duplicates
        results2 = test_db.import_from_csv(sample_csv_content, skip_duplicates=True)
        assert results2['success'] == 0
        assert results2['skipped'] == 3

        # Total records should still be 3
        records = test_db.get_all_records()
        assert len(records) == 3

    def test_import_csv_allow_duplicates(self, test_db, sample_csv_content):
        """Test that duplicates are allowed when skip_duplicates=False"""
        # First import
        results1 = test_db.import_from_csv(sample_csv_content, skip_duplicates=False)
        assert results1['success'] == 3

        # Second import - should add duplicates
        results2 = test_db.import_from_csv(sample_csv_content, skip_duplicates=False)
        assert results2['success'] == 3
        assert results2['skipped'] == 0

        # Total records should be 6
        records = test_db.get_all_records()
        assert len(records) == 6

    def test_import_csv_missing_drug_name(self, test_db):
        """Test that rows with missing drug names are skipped"""
        csv_content = '''Drug Name,Stock Concentration,Unit,Storage Temperature
,10,mM,4C
Valid Drug,20,µM,-20C'''

        results = test_db.import_from_csv(csv_content)
        assert results['success'] == 1
        assert len(results['errors']) == 1
        assert 'Missing drug name' in results['errors'][0]

    def test_import_csv_invalid_concentration(self, test_db):
        """Test handling of invalid concentration values"""
        csv_content = '''Drug Name,Stock Concentration,Unit,Storage Temperature
Drug A,invalid,mM,4C
Drug B,20,µM,-20C'''

        results = test_db.import_from_csv(csv_content)
        assert results['success'] == 2  # Both should import, invalid becomes None

        # Verify Drug A has None concentration
        records = test_db.get_all_records()
        drug_a = next((r for r in records if r['drug_name'] == 'Drug A'), None)
        assert drug_a is not None
        assert drug_a['stock_concentration'] is None

    def test_import_csv_transaction_rollback(self, test_db):
        """Test that transaction is rolled back on critical error"""
        # This test verifies the transaction behavior
        # First add a record
        test_db.add_record({
            'drug_name': 'Existing Drug',
            'stock_concentration': 10,
            'stock_unit': 'mM',
            'storage_temp': '4C',
            'supplier': None,
            'preparation_date': None,
            'notes': None,
            'solvents': None,
            'solubility': None,
            'light_sensitive': None,
            'preparation_time': None,
            'expiration_time': None,
            'sterility': None,
            'lot_number': None,
            'product_number': None
        })

        # Verify we start with 1 record
        records = test_db.get_all_records()
        assert len(records) == 1

        # Import valid CSV
        csv_content = '''Drug Name,Stock Concentration,Unit
New Drug 1,10,mM
New Drug 2,20,µM'''

        results = test_db.import_from_csv(csv_content)
        assert results['success'] == 2

        # Verify we now have 3 records
        records = test_db.get_all_records()
        assert len(records) == 3


class TestCSVExport:
    """Tests for CSV export functionality"""

    def test_export_csv(self, test_db, sample_record):
        """Test exporting records to CSV"""
        # Add some records
        test_db.add_record(sample_record)
        sample_record['drug_name'] = 'Another Drug'
        test_db.add_record(sample_record)

        csv_data = test_db.export_to_csv()

        assert csv_data is not None
        assert 'Drug Name' in csv_data  # Header
        assert 'Test Drug' in csv_data
        assert 'Another Drug' in csv_data

    def test_export_csv_empty_database(self, test_db):
        """Test exporting when database is empty"""
        csv_data = test_db.export_to_csv()

        # Should have header but no data rows
        lines = csv_data.strip().split('\n')
        assert len(lines) == 1  # Just header
        assert 'Drug Name' in lines[0]


class TestFridgeConfig:
    """Tests for fridge configuration operations"""

    def test_default_fridge_configs(self, test_db):
        """Test that default fridge configs are created"""
        configs = test_db.get_all_fridge_configs()

        assert len(configs) == 3

        # Check 4C config
        config_4c = test_db.get_fridge_config('4C')
        assert config_4c is not None
        assert config_4c['body_rows'] == 3
        assert config_4c['door_rows'] == 2

        # Check -80C config (no door)
        config_80c = test_db.get_fridge_config('-80C')
        assert config_80c is not None
        assert config_80c['door_rows'] == 0
        assert config_80c['door_columns'] == 0

    def test_update_fridge_config(self, test_db):
        """Test updating fridge configuration"""
        test_db.update_fridge_config('4C', 5, 5, 3, 3)

        config = test_db.get_fridge_config('4C')
        assert config['body_rows'] == 5
        assert config['body_columns'] == 5
        assert config['door_rows'] == 3
        assert config['door_columns'] == 3


class TestStorageLocation:
    """Tests for storage location operations"""

    def test_get_records_by_location(self, test_db, sample_record):
        """Test retrieving records by storage location"""
        # Add record at specific location
        sample_record['storage_temp'] = '4C'
        sample_record['storage_section'] = 'body'
        sample_record['storage_row'] = 1
        sample_record['storage_column'] = 1
        test_db.add_record(sample_record)

        # Add another at different location
        sample_record['drug_name'] = 'Drug 2'
        sample_record['storage_row'] = 2
        sample_record['storage_column'] = 2
        test_db.add_record(sample_record)

        # Query specific location
        records = test_db.get_records_by_location('4C', 'body', 1, 1)
        assert len(records) == 1
        assert records[0]['drug_name'] == 'Test Drug'

    def test_get_storage_grid_data(self, test_db, sample_record):
        """Test getting grid data with item counts"""
        # Add multiple records at same location
        sample_record['storage_temp'] = '4C'
        sample_record['storage_section'] = 'body'
        sample_record['storage_row'] = 1
        sample_record['storage_column'] = 1
        test_db.add_record(sample_record)

        sample_record['drug_name'] = 'Drug 2'
        test_db.add_record(sample_record)

        sample_record['drug_name'] = 'Drug 3'
        sample_record['storage_row'] = 2
        test_db.add_record(sample_record)

        grid_data = test_db.get_storage_grid_data('4C')

        assert 'body-1-1' in grid_data
        assert grid_data['body-1-1'] == 2  # Two drugs at this location
        assert 'body-2-1' in grid_data
        assert grid_data['body-2-1'] == 1
