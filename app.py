"""
Flask Web Application for Lab Management System
Main application file with routes and API endpoints
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from database import Database
from werkzeug.utils import secure_filename
import io
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lab-management-secret-key-2026'
app.config['UPLOAD_FOLDER'] = 'static/fridge_photos'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize database
db = Database('lab_management.db')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.context_processor
def inject_settings():
    """Make settings available to all templates"""
    settings = db.get_all_settings()
    return {'lab_settings': settings}


@app.route('/')
def index():
    """Main page - displays all records and fridge visualization"""
    records = db.get_all_records()
    fridge_configs = db.get_all_fridge_configs()
    return render_template('index.html', records=records, fridge_configs=fridge_configs)


@app.route('/api/records', methods=['GET'])
def get_records():
    """API endpoint to get all records"""
    search_term = request.args.get('search', '')
    filter_temp = request.args.get('temperature', None)

    if search_term:
        records = db.search_records(search_term, filter_temp)
    else:
        records = db.get_all_records()
        if filter_temp:
            records = [r for r in records if r['storage_temp'] == filter_temp]

    return jsonify([dict(r) for r in records])


@app.route('/api/record/<int:record_id>', methods=['GET'])
def get_record(record_id):
    """API endpoint to get a single record"""
    record = db.get_record_by_id(record_id)
    if record:
        return jsonify(dict(record))
    return jsonify({'error': 'Record not found'}), 404


@app.route('/api/record', methods=['POST'])
def add_record():
    """API endpoint to add a new record"""
    data = request.json

    # Validation
    if not data.get('drug_name'):
        return jsonify({'error': 'Drug name is required'}), 400

    # Validate storage location fridge matches storage temperature
    storage_section = data.get('storage_section')
    storage_temp = data.get('storage_temp')

    if storage_section and storage_temp:
        # Ensure the storage location is valid for the temperature
        if storage_temp == '-80C' and storage_section == 'door':
            return jsonify({'error': '-80C freezers do not have door storage'}), 400

    try:
        record_id = db.add_record(data)
        return jsonify({'success': True, 'id': record_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/record/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    """API endpoint to update a record"""
    data = request.json

    # Validation
    if not data.get('drug_name'):
        return jsonify({'error': 'Drug name is required'}), 400

    # Validate storage location
    storage_section = data.get('storage_section')
    storage_temp = data.get('storage_temp')

    if storage_section and storage_temp:
        if storage_temp == '-80C' and storage_section == 'door':
            return jsonify({'error': '-80C freezers do not have door storage'}), 400

    try:
        db.update_record(record_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    """API endpoint to delete a record"""
    try:
        db.delete_record(record_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fridge/grid/<temp_key>', methods=['GET'])
def get_fridge_grid(temp_key):
    """API endpoint to get fridge grid data"""
    config = db.get_fridge_config(temp_key)
    grid_data = db.get_storage_grid_data(temp_key)

    if config:
        return jsonify({
            'config': dict(config),
            'grid_data': grid_data
        })
    return jsonify({'error': 'Configuration not found'}), 404


@app.route('/api/fridge/config', methods=['GET'])
def get_all_fridge_configs():
    """API endpoint to get all fridge configurations"""
    configs = db.get_all_fridge_configs()
    return jsonify([dict(c) for c in configs])


@app.route('/api/fridge/config/<temp_key>', methods=['PUT'])
def update_fridge_config(temp_key):
    """API endpoint to update fridge configuration"""
    data = request.json

    body_rows = data.get('body_rows', 3)
    body_cols = data.get('body_columns', 3)
    door_rows = data.get('door_rows', 2)
    door_cols = data.get('door_columns', 2)

    # -80C should not have door storage
    if temp_key == '-80C':
        door_rows = 0
        door_cols = 0

    try:
        db.update_fridge_config(temp_key, body_rows, body_cols, door_rows, door_cols)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/location/<temp_key>/<section>/<int:row>/<int:col>', methods=['GET'])
def get_location_items(temp_key, section, row, col):
    """API endpoint to get items at a specific storage location"""
    records = db.get_records_by_location(temp_key, section, row, col)
    return jsonify([dict(r) for r in records])


@app.route('/calculator/dilution')
def dilution_calculator():
    """Dilution calculator page"""
    records = db.get_all_records()
    # Convert Row objects to dicts for JSON serialization
    records_list = [dict(r) for r in records]
    return render_template('dilution_calculator.html', records=records_list)


@app.route('/calculator/actual-concentration')
def actual_concentration_calculator():
    """Actual concentration calculator page"""
    records = db.get_all_records()
    # Convert Row objects to dicts for JSON serialization
    records_list = [dict(r) for r in records]
    return render_template('actual_concentration_calculator.html', records=records_list)


def get_unit_conversion_factor(from_unit, to_unit):
    """Get the conversion factor to convert from one unit to another.

    Returns the factor to multiply by, or None if units are incompatible.
    """
    # Define unit families and their base conversions
    # Molar units (base: M)
    molar_units = {
        'M': 1,
        'mM': 1e-3,
        'µM': 1e-6,
        'nM': 1e-9,
        'pM': 1e-12
    }

    # Mass/volume units (base: g/mL)
    # Note: µg/µL = 1000 µg/mL = 1 mg/mL
    mass_vol_units = {
        'g/mL': 1,
        'mg/mL': 1e-3,
        'µg/mL': 1e-6,
        'ng/mL': 1e-9,
        'pg/mL': 1e-12,
        'mg/µL': 1,        # 1 mg/µL = 1 g/mL
        'µg/µL': 1e-3,     # 1 µg/µL = 1 mg/mL
        'ng/µL': 1e-6      # 1 ng/µL = 1 µg/mL
    }

    # Dimensionless units (must match exactly)
    dimensionless_units = {'%', 'X'}

    # Activity units (base: U/mL)
    activity_units = {
        'U/mL': 1,
        'IU/mL': 1  # Treat as equivalent for calculation purposes
    }

    # Check if units are the same
    if from_unit == to_unit:
        return 1.0

    # Check molar units
    if from_unit in molar_units and to_unit in molar_units:
        return molar_units[from_unit] / molar_units[to_unit]

    # Check mass/volume units
    if from_unit in mass_vol_units and to_unit in mass_vol_units:
        return mass_vol_units[from_unit] / mass_vol_units[to_unit]

    # Check activity units
    if from_unit in activity_units and to_unit in activity_units:
        return activity_units[from_unit] / activity_units[to_unit]

    # Check dimensionless units
    if from_unit in dimensionless_units and to_unit in dimensionless_units:
        if from_unit == to_unit:
            return 1.0
        return None  # Can't convert between % and X

    # Units are incompatible
    return None


@app.route('/api/calculator/dilution', methods=['POST'])
def calculate_dilution():
    """API endpoint for dilution calculations"""
    data = request.json

    # Validate required fields exist
    required_fields = ['stock_concentration', 'final_concentration', 'final_volume']
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400

    try:
        stock_conc = float(data['stock_concentration'])
        final_conc = float(data['final_concentration'])
        final_volume = float(data['final_volume'])
    except (ValueError, TypeError):
        return jsonify({'error': 'All concentration and volume values must be valid numbers'}), 400

    # Validate positive values
    if stock_conc <= 0:
        return jsonify({'error': 'Stock concentration must be a positive number'}), 400
    if final_conc <= 0:
        return jsonify({'error': 'Final concentration must be a positive number'}), 400
    if final_volume <= 0:
        return jsonify({'error': 'Final volume must be a positive number'}), 400

    # Validate reasonable ranges (prevent overflow/underflow)
    max_value = 1e12  # 1 trillion
    min_value = 1e-12  # 1 trillionth
    if stock_conc > max_value or final_conc > max_value or final_volume > max_value:
        return jsonify({'error': f'Values cannot exceed {max_value}'}), 400
    if stock_conc < min_value or final_conc < min_value or final_volume < min_value:
        return jsonify({'error': f'Values cannot be less than {min_value}'}), 400

    stock_unit = data.get('stock_unit', 'µM')
    final_unit = data.get('final_unit', 'µM')

    # Convert final concentration to stock unit for comparison and calculation
    conversion_factor = get_unit_conversion_factor(final_unit, stock_unit)

    if conversion_factor is None:
        return jsonify({'error': f'Cannot convert between {final_unit} and {stock_unit}. Units must be compatible (e.g., both molar or both mass/volume).'}), 400

    # Convert final concentration to same unit as stock
    final_conc_converted = final_conc * conversion_factor

    # Validate logical constraints (after unit conversion)
    if final_conc_converted > stock_conc:
        return jsonify({'error': f'Final concentration ({final_conc} {final_unit}) cannot exceed stock concentration ({stock_conc} {stock_unit}) - cannot concentrate by dilution'}), 400

    # C1V1 = C2V2, solve for V1 (using converted units)
    volume_stock = (final_conc_converted * final_volume) / stock_conc

    # Calculate volume of solvent
    volume_solvent = final_volume - volume_stock

    return jsonify({
        'success': True,
        'volume_stock': round(volume_stock, 6),
        'volume_solvent': round(volume_solvent, 6),
        'stock_concentration': stock_conc,
        'final_concentration': final_conc,
        'final_concentration_converted': round(final_conc_converted, 6),
        'final_volume': final_volume,
        'stock_unit': stock_unit,
        'final_unit': final_unit
    })


@app.route('/api/calculator/actual-concentration', methods=['POST'])
def calculate_actual_concentration():
    """API endpoint for actual concentration calculations"""
    data = request.json

    # Validate media_volume exists
    if 'media_volume' not in data or data['media_volume'] is None or data['media_volume'] == '':
        return jsonify({'error': 'Media volume is required'}), 400

    try:
        media_volume = float(data['media_volume'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Media volume must be a valid number'}), 400

    # Validate media_volume is positive
    if media_volume <= 0:
        return jsonify({'error': 'Media volume must be a positive number'}), 400

    # Validate reasonable range
    max_value = 1e12
    min_value = 1e-12
    if media_volume > max_value:
        return jsonify({'error': f'Media volume cannot exceed {max_value}'}), 400
    if media_volume < min_value:
        return jsonify({'error': f'Media volume cannot be less than {min_value}'}), 400

    # Validate components exist and is a list
    components = data.get('components')
    if not components or not isinstance(components, list):
        return jsonify({'error': 'At least one component is required'}), 400

    results = []
    for idx, comp in enumerate(components, start=1):
        # Validate required component fields
        if 'stock_concentration' not in comp or comp['stock_concentration'] is None or comp['stock_concentration'] == '':
            return jsonify({'error': f'Component {idx}: Stock concentration is required'}), 400
        if 'volume' not in comp or comp['volume'] is None or comp['volume'] == '':
            return jsonify({'error': f'Component {idx}: Volume is required'}), 400

        try:
            stock_conc = float(comp['stock_concentration'])
            volume = float(comp['volume'])
        except (ValueError, TypeError):
            return jsonify({'error': f'Component {idx}: Stock concentration and volume must be valid numbers'}), 400

        # Validate positive values
        if stock_conc <= 0:
            return jsonify({'error': f'Component {idx}: Stock concentration must be a positive number'}), 400
        if volume <= 0:
            return jsonify({'error': f'Component {idx}: Volume must be a positive number'}), 400

        # Validate reasonable ranges
        if stock_conc > max_value or volume > max_value:
            return jsonify({'error': f'Component {idx}: Values cannot exceed {max_value}'}), 400
        if stock_conc < min_value or volume < min_value:
            return jsonify({'error': f'Component {idx}: Values cannot be less than {min_value}'}), 400

        volume_unit = comp.get('volume_unit', 'mL')

        # Convert volume to mL
        if volume_unit == 'µL':
            volume_ml = volume / 1000.0
        else:
            volume_ml = volume

        final_volume = media_volume + volume_ml

        # C2 = (C1 * V1) / V2
        final_conc = (stock_conc * volume_ml) / final_volume

        results.append({
            'name': comp.get('name', f'Component {idx}'),
            'stock_concentration': stock_conc,
            'stock_unit': comp.get('stock_unit', ''),
            'volume_added': volume,
            'volume_unit': volume_unit,
            'final_concentration': round(final_conc, 6),
            'final_volume': round(final_volume, 4)
        })

    return jsonify({
        'success': True,
        'media_volume': media_volume,
        'results': results
    })


@app.route('/export/csv')
def export_csv():
    """Export all records to CSV"""
    csv_data = db.export_to_csv()

    output = io.BytesIO()
    output.write(csv_data.encode('utf-8'))
    output.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'lab_inventory_{timestamp}.csv'

    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


@app.route('/import/csv', methods=['POST'])
def import_csv():
    """Import records from CSV file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400

    try:
        # Read file content
        csv_content = file.read().decode('utf-8')

        # Get skip_duplicates option
        skip_duplicates = request.form.get('skip_duplicates', 'true').lower() == 'true'

        # Import data
        results = db.import_from_csv(csv_content, skip_duplicates)

        return jsonify({
            'success': True,
            'imported': results['success'],
            'skipped': results['skipped'],
            'errors': results['errors']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/import-export')
def import_export_page():
    """Import/Export page"""
    return render_template('import_export.html')


# ========== VISUAL FRIDGE LAYOUT ROUTES ==========

@app.route('/visual-fridge-display')
def visual_fridge_display():
    """Visual fridge display page - view and interact with photo-based layouts"""
    return render_template('visual_fridge_display.html')


@app.route('/api/layout/upload', methods=['POST'])
def upload_layout_photo():
    """Upload a fridge photo and create layout"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo uploaded'}), 400

    file = request.files['photo']
    temp_key = request.form.get('temp_key')
    section = request.form.get('section')

    if not temp_key or not section:
        return jsonify({'error': 'Temperature and section are required'}), 400

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Use JPG, PNG, or GIF'}), 400

    try:
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f'{temp_key}_{section}_{timestamp}{file_ext}')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save file
        file.save(filepath)

        # Create or update layout in database
        layout_id = db.create_or_update_layout(temp_key, section, filename)

        return jsonify({
            'success': True,
            'layout_id': layout_id,
            'filename': filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/layout/<int:layout_id>/regions', methods=['GET'])
def get_layout_regions(layout_id):
    """Get all regions for a layout"""
    try:
        regions = db.get_regions_for_layout(layout_id)
        return jsonify([dict(r) for r in regions])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/layout/<int:layout_id>/region', methods=['POST'])
def create_region(layout_id):
    """Create a new region on a layout"""
    data = request.json

    required = ['region_name', 'x', 'y', 'width', 'height']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        region_id = db.create_region(
            layout_id,
            data['region_name'],
            int(data['x']),
            int(data['y']),
            int(data['width']),
            int(data['height'])
        )
        return jsonify({'success': True, 'region_id': region_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/region/<int:region_id>', methods=['PUT'])
def update_region(region_id):
    """Update a region"""
    data = request.json

    required = ['region_name', 'x', 'y', 'width', 'height']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        db.update_region(
            region_id,
            data['region_name'],
            int(data['x']),
            int(data['y']),
            int(data['width']),
            int(data['height'])
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/region/<int:region_id>', methods=['DELETE'])
def delete_region(region_id):
    """Delete a region"""
    try:
        db.delete_region(region_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/region/<int:region_id>/items', methods=['GET'])
def get_region_items(region_id):
    """Get all items in a region"""
    try:
        items = db.get_items_in_region(region_id)
        return jsonify([dict(item) for item in items])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/region/<int:region_id>/assign', methods=['POST'])
def assign_to_region(region_id):
    """Assign an item to a region"""
    data = request.json
    drug_id = data.get('drug_id')

    if not drug_id:
        return jsonify({'error': 'drug_id is required'}), 400

    try:
        db.assign_item_to_region(drug_id, region_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/layout/<temp_key>/<section>', methods=['GET'])
def get_layout_by_temp_section(temp_key, section):
    """Get layout and regions for a specific temp/section"""
    try:
        layout = db.get_layout(temp_key, section)
        if not layout:
            return jsonify({'error': 'Layout not found'}), 404

        regions = db.get_regions_for_layout(layout['id'])
        occupancy = db.get_region_occupancy(layout['id'])

        return jsonify({
            'layout': dict(layout),
            'regions': [dict(r) for r in regions],
            'occupancy': [dict(o) for o in occupancy]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== SCHEMATIC LAYOUT ROUTES ==========

@app.route('/schematic-layout-builder')
def schematic_layout_builder():
    """Schematic fridge layout builder page"""
    return render_template('schematic_layout_builder.html')


@app.route('/api/schematic/<temp_key>/<section>', methods=['GET'])
def get_schematic_layout(temp_key, section):
    """Get schematic layout and zones for a specific temp/section (legacy, no fridge_id)"""
    try:
        layout = db.get_schematic_layout(temp_key, section)
        if not layout:
            return jsonify({'layout': None, 'zones': [], 'occupancy': []})

        zones = db.get_schematic_zones(layout['id'])
        occupancy = db.get_zone_occupancy(layout['id'])

        return jsonify({
            'layout': dict(layout),
            'zones': [dict(z) for z in zones],
            'occupancy': [dict(o) for o in occupancy]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schematic/fridge/<int:fridge_id>/<section>', methods=['GET'])
def get_schematic_layout_by_fridge(fridge_id, section):
    """Get schematic layout and zones for a specific fridge and section"""
    try:
        layout = db.get_schematic_layout_by_fridge(fridge_id, section)
        if not layout:
            return jsonify({'layout': None, 'zones': [], 'occupancy': []})

        zones = db.get_schematic_zones(layout['id'])
        occupancy = db.get_zone_occupancy(layout['id'])

        return jsonify({
            'layout': dict(layout),
            'zones': [dict(z) for z in zones],
            'occupancy': [dict(o) for o in occupancy]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schematic/create', methods=['POST'])
def create_schematic_layout():
    """Create a new schematic layout"""
    data = request.json
    temp_key = data.get('temp_key')
    section = data.get('section')
    layout_name = data.get('layout_name')
    fridge_id = data.get('fridge_id')

    if not temp_key or not section:
        return jsonify({'error': 'temp_key and section are required'}), 400

    try:
        layout_id = db.create_schematic_layout(temp_key, section, layout_name, fridge_id=fridge_id)
        return jsonify({'success': True, 'layout_id': layout_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schematic/<int:layout_id>/zones', methods=['POST'])
def save_schematic_zones(layout_id):
    """Save all zones for a schematic layout (replaces existing)"""
    data = request.json
    zones = data.get('zones', [])

    try:
        # Clear existing zones
        db.clear_schematic_zones(layout_id)

        # Add new zones
        for zone in zones:
            db.add_schematic_zone(
                layout_id,
                zone['zone_name'],
                zone['row_index'],
                zone['col_index'],
                zone.get('col_span', 1),
                zone.get('row_span', 1),
                zone.get('color', '#e3f2fd')
            )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schematic/upload-reference', methods=['POST'])
def upload_schematic_reference():
    """Upload a reference photo for schematic layout"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo uploaded'}), 400

    file = request.files['photo']
    layout_id = request.form.get('layout_id')

    if not layout_id:
        return jsonify({'error': 'layout_id is required'}), 400

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f'ref_{layout_id}_{timestamp}{file_ext}')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Update layout with reference photo
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE fridge_schematic_layouts
            SET reference_photo = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (filename, layout_id))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schematic/zone/<int:zone_id>/items', methods=['GET'])
def get_schematic_zone_items(zone_id):
    """Get all items in a schematic zone"""
    try:
        items = db.get_items_in_zone(zone_id)
        return jsonify([dict(item) for item in items])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schematic/zone/<int:zone_id>/assign', methods=['POST'])
def assign_to_schematic_zone(zone_id):
    """Assign an item to a schematic zone"""
    data = request.json
    drug_id = data.get('drug_id')

    if not drug_id:
        return jsonify({'error': 'drug_id is required'}), 400

    try:
        db.assign_item_to_zone(drug_id, zone_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== ANTIBODY MANAGEMENT ROUTES ==========

@app.route('/antibodies')
def antibodies_page():
    """Antibody management page"""
    return render_template('antibodies.html')


@app.route('/api/antibodies/primary', methods=['GET'])
def get_primary_antibodies():
    """Get all primary antibodies"""
    antibodies = db.get_all_primary_antibodies()
    return jsonify([dict(ab) for ab in antibodies])


@app.route('/api/antibodies/primary/<int:ab_id>', methods=['GET'])
def get_primary_antibody(ab_id):
    """Get a single primary antibody"""
    antibody = db.get_primary_antibody_by_id(ab_id)
    if antibody:
        return jsonify(dict(antibody))
    return jsonify({'error': 'Antibody not found'}), 404


@app.route('/api/antibodies/primary', methods=['POST'])
def add_primary_antibody():
    """Add a new primary antibody"""
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'Antibody name is required'}), 400

    try:
        ab_id = db.add_primary_antibody(data)
        return jsonify({'success': True, 'id': ab_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/antibodies/primary/<int:ab_id>', methods=['PUT'])
def update_primary_antibody(ab_id):
    """Update a primary antibody"""
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'Antibody name is required'}), 400

    try:
        db.update_primary_antibody(ab_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/antibodies/primary/<int:ab_id>', methods=['DELETE'])
def delete_primary_antibody(ab_id):
    """Delete a primary antibody"""
    try:
        db.delete_primary_antibody(ab_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/antibodies/secondary', methods=['GET'])
def get_secondary_antibodies():
    """Get all secondary antibodies"""
    antibodies = db.get_all_secondary_antibodies()
    return jsonify([dict(ab) for ab in antibodies])


@app.route('/api/antibodies/secondary/<int:ab_id>', methods=['GET'])
def get_secondary_antibody(ab_id):
    """Get a single secondary antibody"""
    antibody = db.get_secondary_antibody_by_id(ab_id)
    if antibody:
        return jsonify(dict(antibody))
    return jsonify({'error': 'Antibody not found'}), 404


@app.route('/api/antibodies/secondary', methods=['POST'])
def add_secondary_antibody():
    """Add a new secondary antibody"""
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'Antibody name is required'}), 400

    try:
        ab_id = db.add_secondary_antibody(data)
        return jsonify({'success': True, 'id': ab_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/antibodies/secondary/<int:ab_id>', methods=['PUT'])
def update_secondary_antibody(ab_id):
    """Update a secondary antibody"""
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'Antibody name is required'}), 400

    try:
        db.update_secondary_antibody(ab_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/antibodies/secondary/<int:ab_id>', methods=['DELETE'])
def delete_secondary_antibody(ab_id):
    """Delete a secondary antibody"""
    try:
        db.delete_secondary_antibody(ab_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/antibodies/match/<int:primary_id>', methods=['GET'])
def find_matching_secondaries(primary_id):
    """Find secondary antibodies compatible with a given primary"""
    try:
        matches = db.find_matching_secondaries(primary_id)
        return jsonify(matches)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== SETTINGS ROUTES ==========

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all settings"""
    settings = db.get_all_settings()
    return jsonify(settings)


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update settings"""
    data = request.json
    try:
        for key, value in data.items():
            db.set_setting(key, value)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/<key>', methods=['GET'])
def get_setting(key):
    """Get a specific setting"""
    value = db.get_setting(key)
    return jsonify({'key': key, 'value': value})


# ========== FRIDGE MANAGEMENT ROUTES ==========

@app.route('/api/fridges', methods=['GET'])
def get_fridges():
    """Get all user-defined fridges"""
    fridges = db.get_all_fridges()
    return jsonify([dict(f) for f in fridges])


@app.route('/api/fridges/<int:fridge_id>', methods=['GET'])
def get_fridge(fridge_id):
    """Get a single fridge by ID"""
    fridge = db.get_fridge_by_id(fridge_id)
    if fridge:
        return jsonify(dict(fridge))
    return jsonify({'error': 'Fridge not found'}), 404


@app.route('/api/fridges', methods=['POST'])
def add_fridge():
    """Add a new fridge"""
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'Fridge name is required'}), 400
    if not data.get('temp_type'):
        return jsonify({'error': 'Temperature type is required'}), 400

    try:
        fridge_id = db.add_fridge(data)
        return jsonify({'success': True, 'id': fridge_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fridges/<int:fridge_id>', methods=['PUT'])
def update_fridge(fridge_id):
    """Update a fridge"""
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'Fridge name is required'}), 400
    if not data.get('temp_type'):
        return jsonify({'error': 'Temperature type is required'}), 400

    try:
        db.update_fridge(fridge_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fridges/<int:fridge_id>', methods=['DELETE'])
def delete_fridge(fridge_id):
    """Delete a fridge"""
    try:
        db.delete_fridge(fridge_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fridges/by-temp/<temp_type>', methods=['GET'])
def get_fridges_by_temp(temp_type):
    """Get all fridges of a specific temperature type"""
    fridges = db.get_fridges_by_temp_type(temp_type)
    return jsonify([dict(f) for f in fridges])


if __name__ == '__main__':
    print("="*80)
    print("Lab Management System - Web Interface")
    print("="*80)
    print("Server starting on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop the server")
    print("="*80)
    #app.run(debug=True, host='localhost', port=5000)
    app.run(host='0.0.0.0', port=5000)
