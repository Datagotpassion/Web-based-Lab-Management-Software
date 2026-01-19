"""
Unit tests for calculator endpoints
Tests input validation and calculation correctness
"""

import pytest
import json


class TestDilutionCalculator:
    """Tests for the dilution calculator endpoint"""

    def test_valid_dilution_calculation(self, client):
        """Test a valid dilution calculation"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 100,
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['volume_stock'] == 1.0  # (10 * 10) / 100 = 1
        assert data['volume_solvent'] == 9.0  # 10 - 1 = 9

    def test_missing_stock_concentration(self, client):
        """Test error when stock concentration is missing"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Stock Concentration' in data['error']

    def test_missing_final_concentration(self, client):
        """Test error when final concentration is missing"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 100,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Final Concentration' in data['error']

    def test_missing_final_volume(self, client):
        """Test error when final volume is missing"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 100,
                'final_concentration': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Final Volume' in data['error']

    def test_zero_stock_concentration(self, client):
        """Test error when stock concentration is zero"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 0,
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'positive' in data['error'].lower()

    def test_negative_values(self, client):
        """Test error when values are negative"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': -100,
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'positive' in data['error'].lower()

    def test_final_greater_than_stock(self, client):
        """Test error when final concentration exceeds stock concentration"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 10,
                'final_concentration': 100,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'cannot exceed' in data['error'].lower()

    def test_invalid_string_values(self, client):
        """Test error when values are invalid strings"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 'abc',
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'valid numbers' in data['error'].lower()

    def test_empty_string_values(self, client):
        """Test error when values are empty strings"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': '',
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_extremely_large_values(self, client):
        """Test error when values exceed maximum allowed"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 1e15,
                'final_concentration': 10,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'cannot exceed' in data['error'].lower()

    def test_extremely_small_values(self, client):
        """Test error when values are below minimum allowed"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 1e-15,
                'final_concentration': 1e-16,
                'final_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_units_preserved(self, client):
        """Test that units are preserved in response"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 100,
                'final_concentration': 10,
                'final_volume': 10,
                'stock_unit': 'mg/mL',
                'final_unit': 'µg/mL'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['stock_unit'] == 'mg/mL'
        assert data['final_unit'] == 'µg/mL'

    def test_unit_conversion_mM_to_uM(self, client):
        """Test unit conversion from mM stock to µM final"""
        # Stock: 10 mM, Final: 100 µM (= 0.1 mM), Volume: 10 mL
        # V1 = (0.1 * 10) / 10 = 0.1 mL
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 10,
                'final_concentration': 100,
                'final_volume': 10,
                'stock_unit': 'mM',
                'final_unit': 'µM'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        # 100 µM = 0.1 mM, so V1 = (0.1 * 10) / 10 = 0.1 mL
        assert abs(data['volume_stock'] - 0.1) < 0.0001
        assert abs(data['volume_solvent'] - 9.9) < 0.0001

    def test_unit_conversion_M_to_nM(self, client):
        """Test unit conversion from M stock to nM final"""
        # Stock: 1 M, Final: 1000 nM (= 1 µM = 0.000001 M), Volume: 10 mL
        # V1 = (0.000001 * 10) / 1 = 0.00001 mL = 0.01 µL
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 1,
                'final_concentration': 1000,
                'final_volume': 10,
                'stock_unit': 'M',
                'final_unit': 'nM'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        # 1000 nM = 1e-6 M, V1 = (1e-6 * 10) / 1 = 1e-5 mL
        assert abs(data['volume_stock'] - 0.00001) < 0.0000001

    def test_unit_conversion_mg_mL_to_ug_mL(self, client):
        """Test unit conversion for mass/volume units"""
        # Stock: 10 mg/mL, Final: 100 µg/mL (= 0.1 mg/mL), Volume: 10 mL
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 10,
                'final_concentration': 100,
                'final_volume': 10,
                'stock_unit': 'mg/mL',
                'final_unit': 'µg/mL'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        # 100 µg/mL = 0.1 mg/mL, V1 = (0.1 * 10) / 10 = 0.1 mL
        assert abs(data['volume_stock'] - 0.1) < 0.0001

    def test_incompatible_units_rejected(self, client):
        """Test that incompatible units are rejected"""
        # Can't convert between mM (molar) and mg/mL (mass/volume)
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 10,
                'final_concentration': 1,
                'final_volume': 10,
                'stock_unit': 'mM',
                'final_unit': 'mg/mL'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Cannot convert' in data['error']

    def test_final_exceeds_stock_after_conversion(self, client):
        """Test error when final exceeds stock after unit conversion"""
        # Stock: 1 µM, Final: 10 mM = 10000 µM (exceeds stock)
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 1,
                'final_concentration': 10,
                'final_volume': 10,
                'stock_unit': 'µM',
                'final_unit': 'mM'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'cannot exceed' in data['error'].lower()

    def test_same_units_work(self, client):
        """Test calculation with same units"""
        response = client.post('/api/calculator/dilution',
            data=json.dumps({
                'stock_concentration': 100,
                'final_concentration': 10,
                'final_volume': 10,
                'stock_unit': 'µM',
                'final_unit': 'µM'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['volume_stock'] == 1.0


class TestActualConcentrationCalculator:
    """Tests for the actual concentration calculator endpoint"""

    def test_valid_calculation(self, client):
        """Test a valid actual concentration calculation"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 100,
                        'stock_unit': 'mM',
                        'volume': 1,
                        'volume_unit': 'mL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['results']) == 1
        # C2 = (100 * 1) / (10 + 1) = 9.090909...
        assert abs(data['results'][0]['final_concentration'] - 9.090909) < 0.001

    def test_missing_media_volume(self, client):
        """Test error when media volume is missing"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 100,
                        'volume': 1,
                        'volume_unit': 'mL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Media volume' in data['error']

    def test_zero_media_volume(self, client):
        """Test error when media volume is zero"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 0,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 100,
                        'volume': 1,
                        'volume_unit': 'mL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'positive' in data['error'].lower()

    def test_negative_media_volume(self, client):
        """Test error when media volume is negative"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': -10,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 100,
                        'volume': 1,
                        'volume_unit': 'mL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'positive' in data['error'].lower()

    def test_missing_components(self, client):
        """Test error when components list is missing"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'component' in data['error'].lower()

    def test_empty_components(self, client):
        """Test error when components list is empty"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': []
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'component' in data['error'].lower()

    def test_component_missing_stock_concentration(self, client):
        """Test error when component is missing stock concentration"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': [
                    {
                        'name': 'Drug A',
                        'volume': 1,
                        'volume_unit': 'mL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Component 1' in data['error']
        assert 'Stock concentration' in data['error']

    def test_component_missing_volume(self, client):
        """Test error when component is missing volume"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 100
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Component 1' in data['error']
        assert 'Volume' in data['error']

    def test_component_negative_stock_concentration(self, client):
        """Test error when component has negative stock concentration"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': -100,
                        'volume': 1,
                        'volume_unit': 'mL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Component 1' in data['error']
        assert 'positive' in data['error'].lower()

    def test_multiple_components(self, client):
        """Test calculation with multiple components"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 100,
                        'stock_unit': 'mM',
                        'volume': 1,
                        'volume_unit': 'mL'
                    },
                    {
                        'name': 'Drug B',
                        'stock_concentration': 50,
                        'stock_unit': 'µM',
                        'volume': 500,
                        'volume_unit': 'µL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['results']) == 2
        assert data['results'][0]['name'] == 'Drug A'
        assert data['results'][1]['name'] == 'Drug B'

    def test_microliter_conversion(self, client):
        """Test that microliters are correctly converted to mL"""
        response = client.post('/api/calculator/actual-concentration',
            data=json.dumps({
                'media_volume': 10,
                'components': [
                    {
                        'name': 'Drug A',
                        'stock_concentration': 1000,
                        'stock_unit': 'mM',
                        'volume': 100,
                        'volume_unit': 'µL'
                    }
                ]
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        # 100 µL = 0.1 mL
        # C2 = (1000 * 0.1) / (10 + 0.1) = 100 / 10.1 = 9.90099...
        assert abs(data['results'][0]['final_concentration'] - 9.90099) < 0.001
        assert abs(data['results'][0]['final_volume'] - 10.1) < 0.001
