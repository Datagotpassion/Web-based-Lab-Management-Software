"""
Pytest fixtures for Lab Management System tests
"""

import pytest
import tempfile
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import Database


@pytest.fixture
def test_db():
    """Create a temporary database for testing"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = Database(db_path)
    yield db

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client(test_db):
    """Create a test client with a temporary database"""
    app.config['TESTING'] = True

    # Patch the database in the app module
    import app as app_module
    original_db = app_module.db
    app_module.db = test_db

    with app.test_client() as client:
        yield client

    # Restore original database
    app_module.db = original_db


@pytest.fixture
def sample_record():
    """Sample drug record for testing"""
    return {
        'drug_name': 'Test Drug',
        'stock_concentration': 10.0,
        'stock_unit': 'mM',
        'storage_temp': '4C',
        'supplier': 'Test Supplier',
        'preparation_date': '2024-01-15',
        'notes': 'Test notes',
        'solvents': 'DMSO',
        'solubility': 'Soluble',
        'light_sensitive': 'No',
        'preparation_time': '10:00',
        'expiration_time': '2025-01-15',
        'sterility': 'Sterile',
        'lot_number': 'LOT123',
        'product_number': 'PROD456',
        'storage_section': 'body',
        'storage_row': 1,
        'storage_column': 1
    }


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for import testing"""
    return '''Drug Name,Stock Concentration,Unit,Storage Temperature,Supplier,Preparation Date,Notes,Solvents,Solubility,Light Sensitive,Preparation Time,Expiration Time,Sterility,Lot Number,Product Number,Storage Section,Storage Row,Storage Column
Drug A,10,mM,4C,Supplier A,2024-01-01,Note A,DMSO,Soluble,No,10:00,2025-01-01,Sterile,LOT001,PROD001,body,1,1
Drug B,20,µM,-20C,Supplier B,2024-02-01,Note B,Water,Soluble,Yes,11:00,2025-02-01,Non-sterile,LOT002,PROD002,door,1,2
Drug C,5,mg/mL,-80C,Supplier C,2024-03-01,Note C,Ethanol,Partially,No,12:00,2025-03-01,Sterile,LOT003,PROD003,body,2,1'''
