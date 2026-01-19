"""
Unit tests for API endpoints
Tests routes, request handling, and response formats
"""

import pytest
import json


class TestRecordAPI:
    """Tests for record CRUD API endpoints"""

    def test_get_records_empty(self, client):
        """Test getting records when database is empty"""
        response = client.get('/api/records')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_add_record(self, client, sample_record):
        """Test adding a new record via API"""
        response = client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'id' in data

    def test_add_record_missing_drug_name(self, client):
        """Test adding a record without drug name"""
        response = client.post('/api/record',
            data=json.dumps({'stock_concentration': 10}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Drug name' in data['error']

    def test_get_record_by_id(self, client, sample_record):
        """Test getting a specific record by ID"""
        # First add a record
        add_response = client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )
        record_id = json.loads(add_response.data)['id']

        # Then get it
        response = client.get(f'/api/record/{record_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['drug_name'] == 'Test Drug'

    def test_get_record_not_found(self, client):
        """Test getting a non-existent record"""
        response = client.get('/api/record/99999')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_record(self, client, sample_record):
        """Test updating a record"""
        # First add a record
        add_response = client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )
        record_id = json.loads(add_response.data)['id']

        # Update it
        sample_record['drug_name'] = 'Updated Drug'
        response = client.put(f'/api/record/{record_id}',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Verify the update
        get_response = client.get(f'/api/record/{record_id}')
        get_data = json.loads(get_response.data)
        assert get_data['drug_name'] == 'Updated Drug'

    def test_delete_record(self, client, sample_record):
        """Test deleting a record"""
        # First add a record
        add_response = client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )
        record_id = json.loads(add_response.data)['id']

        # Delete it
        response = client.delete(f'/api/record/{record_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Verify it's deleted
        get_response = client.get(f'/api/record/{record_id}')
        assert get_response.status_code == 404

    def test_search_records(self, client, sample_record):
        """Test searching records"""
        # Add some records
        sample_record['drug_name'] = 'Aspirin'
        client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        sample_record['drug_name'] = 'Ibuprofen'
        client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        # Search
        response = client.get('/api/records?search=Asp')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['drug_name'] == 'Aspirin'

    def test_filter_by_temperature(self, client, sample_record):
        """Test filtering records by temperature"""
        # Add records with different temperatures
        sample_record['drug_name'] = 'Drug 4C'
        sample_record['storage_temp'] = '4C'
        client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        sample_record['drug_name'] = 'Drug -20C'
        sample_record['storage_temp'] = '-20C'
        client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        # Filter by temperature
        response = client.get('/api/records?temperature=4C')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['drug_name'] == 'Drug 4C'


class TestStorageValidation:
    """Tests for storage location validation"""

    def test_80c_door_storage_rejected(self, client, sample_record):
        """Test that -80C freezer rejects door storage"""
        sample_record['storage_temp'] = '-80C'
        sample_record['storage_section'] = 'door'

        response = client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert '-80C' in data['error']
        assert 'door' in data['error'].lower()

    def test_80c_body_storage_accepted(self, client, sample_record):
        """Test that -80C freezer accepts body storage"""
        sample_record['storage_temp'] = '-80C'
        sample_record['storage_section'] = 'body'

        response = client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        assert response.status_code == 200


class TestFridgeConfigAPI:
    """Tests for fridge configuration API"""

    def test_get_all_configs(self, client):
        """Test getting all fridge configurations"""
        response = client.get('/api/fridge/config')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_get_fridge_grid(self, client):
        """Test getting fridge grid data"""
        response = client.get('/api/fridge/grid/4C')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'config' in data
        assert 'grid_data' in data

    def test_get_fridge_grid_not_found(self, client):
        """Test getting grid for non-existent fridge"""
        response = client.get('/api/fridge/grid/INVALID')

        assert response.status_code == 404

    def test_update_fridge_config(self, client):
        """Test updating fridge configuration"""
        response = client.put('/api/fridge/config/4C',
            data=json.dumps({
                'body_rows': 5,
                'body_columns': 5,
                'door_rows': 3,
                'door_columns': 3
            }),
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify update
        get_response = client.get('/api/fridge/grid/4C')
        data = json.loads(get_response.data)
        assert data['config']['body_rows'] == 5

    def test_80c_config_no_door(self, client):
        """Test that -80C config ignores door settings"""
        response = client.put('/api/fridge/config/-80C',
            data=json.dumps({
                'body_rows': 4,
                'body_columns': 4,
                'door_rows': 2,  # Should be ignored
                'door_columns': 2  # Should be ignored
            }),
            content_type='application/json'
        )

        assert response.status_code == 200

        # Verify door is still 0
        get_response = client.get('/api/fridge/grid/-80C')
        data = json.loads(get_response.data)
        assert data['config']['door_rows'] == 0
        assert data['config']['door_columns'] == 0


class TestLocationAPI:
    """Tests for storage location API"""

    def test_get_location_items(self, client, sample_record):
        """Test getting items at a specific location"""
        # Add a record at a specific location
        sample_record['storage_temp'] = '4C'
        sample_record['storage_section'] = 'body'
        sample_record['storage_row'] = 1
        sample_record['storage_column'] = 1
        client.post('/api/record',
            data=json.dumps(sample_record),
            content_type='application/json'
        )

        # Get items at that location
        response = client.get('/api/location/4C/body/1/1')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['drug_name'] == 'Test Drug'

    def test_get_empty_location(self, client):
        """Test getting items from empty location"""
        response = client.get('/api/location/4C/body/1/1')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 0


class TestPageRoutes:
    """Tests for page routes"""

    def test_index_page(self, client):
        """Test main index page loads"""
        response = client.get('/')
        assert response.status_code == 200

    def test_config_page(self, client):
        """Test config page loads"""
        response = client.get('/config')
        assert response.status_code == 200

    def test_import_export_page(self, client):
        """Test import/export page loads"""
        response = client.get('/import-export')
        assert response.status_code == 200

    def test_dilution_calculator_page(self, client):
        """Test dilution calculator page loads"""
        response = client.get('/calculator/dilution')
        assert response.status_code == 200

    def test_actual_concentration_calculator_page(self, client):
        """Test actual concentration calculator page loads"""
        response = client.get('/calculator/actual-concentration')
        assert response.status_code == 200
