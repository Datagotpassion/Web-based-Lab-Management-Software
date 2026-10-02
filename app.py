"""
Flask Web Application for Lab Management System
Main application file with routes and API endpoints
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from database import Database
from storage import StorageTree, StorageError, KINDS, UNIT_KINDS
import lookup
import functools
import io
import os
import re
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'LABMANAGER_SECRET_KEY', 'lab-management-secret-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Database path is overridable so the same checkout can run against a different
# file on the Pi without editing code.
DB_PATH = os.environ.get('LABMANAGER_DB', 'lab_management.db')

# Read-only mode, for the freezer display.
#
# That instance holds a replica that is periodically overwritten from the lab
# PC. A write accepted there would succeed, look fine, and then be destroyed by
# the next sync -- silent data loss. Refusing the write outright is the honest
# behaviour, so the only place that accepts changes is the machine holding the
# authoritative database.
READ_ONLY = os.environ.get('LABMANAGER_READONLY', '').strip().lower() in (
    '1', 'true', 'yes', 'on')

db = Database(DB_PATH)

# Storage container tree (units > sections > shelves > racks > boxes > ...).
# ensure_schema is idempotent and makes a fresh install come up working.
storage = StorageTree(DB_PATH).ensure_schema()


@app.before_request
def block_writes_when_read_only():
    """Refuse every mutating request on a read-only replica.

    Applied here rather than per-endpoint so a route added later is covered by
    default -- the failure mode of forgetting is silent data loss.
    """
    if READ_ONLY and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        return jsonify({
            'success': False,
            'error': 'This display is read-only. It shows a copy of the lab PC '
                     'database, refreshed periodically. Add or edit records on '
                     'the lab PC.',
        }), 403


@app.context_processor
def inject_settings():
    """Make settings available to all templates"""
    settings = db.get_all_settings()
    return {'lab_settings': settings, 'read_only': READ_ONLY}


@app.route('/')
def index():
    """Main page - records table plus the storage structure overview"""
    records = db.get_all_records()
    return render_template('index.html', records=records)


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

    # The old "-80C has no door" check is gone with the body/door model: door
    # storage is now simply whether a Door section exists on that unit, and a
    # container_id can only ever point at a container that does exist.

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


# ========== STORAGE STRUCTURE EDITOR ==========
#
# These endpoints sit alongside the legacy fridge/zone routes above rather than
# replacing them, so the existing pages keep working while the new structure is
# built up. The legacy routes read fridge_schematic_*; these read the container
# tree in storage_units / storage_containers.


def storage_api(fn):
    """Turn a StorageError into a 400 with its message, which is user-facing."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except StorageError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
    return wrapper


def _body():
    return request.get_json(silent=True) or {}


def _lan_address():
    """This machine's address on the lab network.

    Opening a UDP socket toward an off-subnet address makes the kernel pick
    the outbound interface without sending anything, which beats parsing
    ifconfig and avoids returning 127.0.0.1 the way hostname lookup often
    does. The display shows this so nobody has to hunt for the Pi's address
    after DHCP moves it.
    """
    import socket
    import subprocess

    def usable(addr):
        # Debian maps its own hostname to 127.0.1.1, so a naive lookup yields a
        # loopback address that looks plausible and is useless to anyone trying
        # to reach the machine. Better to report nothing than that.
        return bool(addr) and not addr.startswith('127.')

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 53))
        addr = sock.getsockname()[0]
        if usable(addr):
            return addr
    except OSError:
        pass            # no default route yet, e.g. just after a move
    finally:
        sock.close()

    # Ask the interfaces directly. Works without a default route, which the
    # probe above needs.
    try:
        out = subprocess.run(['hostname', '-I'], capture_output=True, text=True,
                             timeout=5).stdout
        for addr in out.split():
            if usable(addr) and ':' not in addr:
                return addr
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        addr = socket.gethostbyname(socket.gethostname())
        return addr if usable(addr) else None
    except OSError:
        return None


def _last_sync():
    """Timestamp written by sync_to_pi.py each time it confirms this copy.

    Absent on the machine holding the authoritative database, which is never
    synced to.
    """
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), '.last_sync')
        with open(path) as fh:
            return fh.read().strip() or None
    except OSError:
        return None


@app.route('/api/health', methods=['GET'])
def api_health():
    """Liveness plus a quick sanity summary.

    Lets the deployment be checked from the PC without SSH, the same way
    PlateScope's /api/status is used:
        Invoke-RestMethod http://raspberrypi.local:5000/api/health
    """
    try:
        units = storage.list_units()
        containers = storage.flat_list()
        records = db.get_all_records()
        placed = sum(1 for r in records if r['container_id'] is not None)
        import socket
        return jsonify({
            'status': 'ok',
            'read_only': READ_ONLY,
            'hostname': socket.gethostname(),
            'address': _lan_address(),
            'port': int(os.environ.get('LABMANAGER_PORT', '5000')),
            'database': os.path.abspath(DB_PATH),
            'database_mtime': datetime.fromtimestamp(
                os.path.getmtime(DB_PATH)).isoformat(timespec='seconds'),
            # When the copy was last confirmed current. Distinct from
            # database_mtime, which only moves when something actually
            # changed -- a quiet week would otherwise look like a dead sync.
            'last_sync': _last_sync(),
            'units': len(units),
            'containers': len(containers),
            'records': len(records),
            'records_placed': placed,
            'records_unplaced': len(records) - placed,
            'unplaced_items': len(storage.unplaced_items()),
        })
    except Exception as exc:  # surfaced rather than a bare 500
        return jsonify({'status': 'error', 'error': str(exc)}), 500


@app.route('/kiosk')
def kiosk():
    """Freezer-side touch display.

    A separate UI rather than a responsive variant of the desk pages: at
    1024x600 with a finger, the nav, tables and modals of the desk UI are the
    wrong idioms. Read-only by nature -- it answers "where is this?".
    """
    return render_template('kiosk.html')


@app.route('/freezer')
def freezer_map():
    """Spatial view of a storage unit: shelves, racks, and each rack's boxes.

    The same page serves the desk and the freezer-side panel; READ_ONLY
    removes the editing affordances.
    """
    return render_template('freezer.html')


@app.route('/storage-editor')
def storage_editor():
    """Editor for the physical structure of every storage unit."""
    return render_template('storage_editor.html',
                           container_kinds=KINDS, unit_kinds=UNIT_KINDS)


@app.route('/api/storage/tree', methods=['GET'])
@app.route('/api/storage/tree/<int:unit_id>', methods=['GET'])
@storage_api
def api_storage_tree(unit_id=None):
    return jsonify({'units': storage.get_tree(unit_id),
                    'unplaced': storage.unplaced_items()})


@app.route('/api/storage/flat', methods=['GET'])
@storage_api
def api_storage_flat():
    """Flat container list with full paths, for pickers and location labels."""
    return jsonify({'containers': storage.flat_list()})


@app.route('/api/storage/units', methods=['POST'])
@storage_api
def api_create_unit():
    d = _body()
    return jsonify({'success': True, 'unit': storage.create_unit(
        d.get('name'), d.get('kind', 'fridge'), d.get('room'),
        d.get('default_temp_c'), d.get('notes'))}), 201


@app.route('/api/storage/units/<int:unit_id>', methods=['PUT'])
@storage_api
def api_update_unit(unit_id):
    return jsonify({'success': True,
                    'unit': storage.update_unit(unit_id, **_body())})


@app.route('/api/storage/units/<int:unit_id>', methods=['DELETE'])
@storage_api
def api_delete_unit(unit_id):
    return jsonify({'success': True, **storage.delete_unit(unit_id)})


@app.route('/api/storage/containers', methods=['POST'])
@storage_api
def api_create_container():
    d = _body()
    return jsonify({'success': True, 'container': storage.create_container(
        unit_id=d.get('unit_id'), parent_id=d.get('parent_id'),
        kind=d.get('kind', 'shelf'), label=d.get('label'),
        temp_c=d.get('temp_c'), owner_lab=d.get('owner_lab'),
        pos_row=d.get('pos_row'), pos_col=d.get('pos_col'),
        grid_rows=d.get('grid_rows'), grid_cols=d.get('grid_cols'))}), 201


@app.route('/api/storage/containers/bulk', methods=['POST'])
@storage_api
def api_bulk_create_containers():
    d = _body()
    created = storage.bulk_create_children(
        parent_id=d.get('parent_id'), kind=d.get('kind', 'rack'),
        count=int(d.get('count', 0)), scheme=d.get('scheme', 'letters'),
        prefix=d.get('prefix', ''), start=int(d.get('start', 1)))
    return jsonify({'success': True, 'created': created,
                    'count': len(created)}), 201


@app.route('/api/storage/containers/<int:container_id>', methods=['PUT'])
@storage_api
def api_update_container(container_id):
    return jsonify({'success': True,
                    'container': storage.update_container(container_id, **_body())})


@app.route('/api/storage/containers/<int:container_id>', methods=['DELETE'])
@storage_api
def api_delete_container(container_id):
    force = request.args.get('force', '').lower() in ('1', 'true', 'yes')
    return jsonify({'success': True,
                    **storage.delete_container(container_id, force=force)})


@app.route('/api/storage/containers/<int:container_id>/move', methods=['POST'])
@storage_api
def api_move_container(container_id):
    d = _body()
    return jsonify({'success': True, 'container': storage.move_container(
        container_id, d.get('parent_id'), d.get('pos_row'), d.get('pos_col'))})


@app.route('/api/storage/containers/<int:container_id>/reorder', methods=['POST'])
@storage_api
def api_reorder_container(container_id):
    direction = _body().get('direction', 'up')
    return jsonify({'success': True,
                    'container': storage.reorder(container_id, direction)})


@app.route('/api/storage/containers/<int:container_id>/items', methods=['GET'])
@storage_api
def api_container_items(container_id):
    deep = request.args.get('deep', '').lower() in ('1', 'true', 'yes')
    return jsonify({'items': storage.container_items(container_id, deep),
                    'path': storage.path(container_id)})


@app.route('/api/lookup', methods=['POST'])
def api_lookup():
    """Read a supplier's product page and return the fields worth filling in.

    Best effort by nature: how much comes back depends on whether the vendor
    publishes structured product data. Only what was actually found is
    returned, so the caller can fill blanks without overwriting anything
    already typed.
    """
    data = _body()
    url = (data.get('url') or '').strip()
    # Page content supplied by the browser, for vendors this server cannot
    # fetch: some refuse non-browser clients, some build the page in
    # JavaScript. Pasting what the browser already has works for both.
    pasted = (data.get('html') or '').strip()

    if not url and not pasted:
        return jsonify({'success': False, 'error': 'No address given.'}), 400
    # Add a scheme only when one is absent, so pasting "thermofisher.com/..."
    # works without turning "file://..." into a nonsense hostname and a
    # confusing error.
    if url and not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', url):
        url = 'https://' + url
    try:
        found = lookup.extract(url, html=pasted or None)
    except lookup.LookupError_ as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as-is
        return jsonify({'success': False,
                        'error': f'Could not read that page: {exc}'}), 502
    sources = found.pop('_sources', [])
    return jsonify({'success': True, 'fields': found, 'sources': sources})


@app.route('/api/storage/placeable', methods=['GET'])
@storage_api
def api_placeable_items():
    """All items plus their current location, for the box contents picker."""
    return jsonify({'items': storage.placeable_items()})


@app.route('/api/storage/containers/<int:container_id>/items', methods=['POST'])
@storage_api
def api_place_items(container_id):
    """Put several items into one container at once."""
    moved = storage.place_items(_body().get('items', []), container_id)
    return jsonify({'success': True, 'moved': moved})


@app.route('/api/storage/unplace', methods=['POST'])
@storage_api
def api_unplace_items():
    """Take several items out of wherever they are."""
    moved = storage.place_items(_body().get('items', []), None)
    return jsonify({'success': True, 'moved': moved})


@app.route('/api/storage/place', methods=['POST'])
@storage_api
def api_place_item():
    d = _body()
    storage.place_item(d.get('table'), d.get('item_id'), d.get('container_id'))
    return jsonify({'success': True})


if __name__ == '__main__':
    print("="*80)
    print("Lab Management System - Web Interface")
    print("="*80)
    print("Server starting on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop the server")
    print("="*80)
    #app.run(debug=True, host='localhost', port=5000)
    app.run(host='0.0.0.0', port=5000)
