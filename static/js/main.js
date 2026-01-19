// Main JavaScript file for Lab Management System

let allRecords = [];
let currentEditingId = null;

// Initialize on page load
$(document).ready(function() {
    loadRecords();
    loadFridgeDisplays();

    // Search functionality
    $('#searchInput').on('input', function() {
        filterRecords();
    });

    $('#tempFilter').on('change', function() {
        filterRecords();
    });

    // Handle storage temperature change to update door section visibility
    $('#storageTemp').on('change', function() {
        updateStorageSectionOptions();
    });
});

// Load all records
function loadRecords() {
    fetch('/api/records')
        .then(response => response.json())
        .then(records => {
            allRecords = records;
            displayRecords(records);
        })
        .catch(error => {
            console.error('Error loading records:', error);
            alert('Failed to load records');
        });
}

// Display records in table
function displayRecords(records) {
    const tbody = $('#recordsTableBody');
    tbody.empty();

    if (records.length === 0) {
        tbody.append('<tr><td colspan="7" class="text-center text-muted">No records found</td></tr>');
        return;
    }

    records.forEach(record => {
        const tempBadge = getTempBadge(record.storage_temp);
        const location = getLocationDisplay(record);

        const row = `
            <tr>
                <td>${record.id}</td>
                <td><strong>${record.drug_name}</strong></td>
                <td>${record.stock_concentration || '-'} ${record.stock_unit || ''}</td>
                <td>${tempBadge}</td>
                <td>${location}</td>
                <td>${record.supplier || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="editRecord(${record.id})">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRecord(${record.id})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

// Get temperature badge HTML
function getTempBadge(temp) {
    const badges = {
        '4C': '<span class="temp-badge temp-4c">4°C</span>',
        '-20C': '<span class="temp-badge temp-minus20">-20°C</span>',
        '-80C': '<span class="temp-badge temp-minus80">-80°C</span>',
        'RT': '<span class="badge bg-secondary">RT</span>'
    };
    return badges[temp] || temp;
}

// Get location display string
function getLocationDisplay(record) {
    if (record.storage_section && record.storage_row !== null && record.storage_column !== null) {
        return `${record.storage_section.charAt(0).toUpperCase()}${record.storage_section.slice(1)}: R${record.storage_row} C${record.storage_column}`;
    }
    return '-';
}

// Filter records based on search and temperature
function filterRecords() {
    const searchTerm = $('#searchInput').val().toLowerCase();
    const tempFilter = $('#tempFilter').val();

    let filtered = allRecords;

    if (searchTerm) {
        filtered = filtered.filter(record =>
            record.drug_name.toLowerCase().includes(searchTerm) ||
            (record.supplier && record.supplier.toLowerCase().includes(searchTerm)) ||
            (record.notes && record.notes.toLowerCase().includes(searchTerm))
        );
    }

    if (tempFilter) {
        filtered = filtered.filter(record => record.storage_temp === tempFilter);
    }

    displayRecords(filtered);
}

// Show add record modal
function showAddRecordModal() {
    currentEditingId = null;
    $('#recordModalTitle').text('Add New Record');
    $('#recordForm')[0].reset();
    $('#recordId').val('');
    $('#recordModal').modal('show');
}

// Edit record
function editRecord(id) {
    fetch(`/api/record/${id}`)
        .then(response => response.json())
        .then(record => {
            currentEditingId = id;
            $('#recordModalTitle').text('Edit Record');

            // Fill form fields
            $('#recordId').val(record.id);
            $('#drugName').val(record.drug_name);
            $('#stockConcentration').val(record.stock_concentration || '');
            $('#stockUnit').val(record.stock_unit || 'µM');
            $('#storageTemp').val(record.storage_temp || '4C');
            $('#supplier').val(record.supplier || '');
            $('#preparationDate').val(record.preparation_date || '');
            $('#lotNumber').val(record.lot_number || '');
            $('#productNumber').val(record.product_number || '');
            $('#sterility').val(record.sterility || '');
            $('#lightSensitive').val(record.light_sensitive || '');
            $('#solvents').val(record.solvents || '');
            $('#solubility').val(record.solubility || '');
            $('#preparationTime').val(record.preparation_time || '');
            $('#expirationTime').val(record.expiration_time || '');
            $('#storageSection').val(record.storage_section || '');
            $('#storageRow').val(record.storage_row || '');
            $('#storageColumn').val(record.storage_column || '');
            $('#notes').val(record.notes || '');

            updateStorageSectionOptions();
            $('#recordModal').modal('show');
        })
        .catch(error => {
            console.error('Error loading record:', error);
            alert('Failed to load record');
        });
}

// Save record (add or update)
function saveRecord() {
    const drugName = $('#drugName').val().trim();

    if (!drugName) {
        alert('Drug name is required');
        return;
    }

    const storageTemp = $('#storageTemp').val();
    const storageSection = $('#storageSection').val();

    // Validate -80C doesn't have door storage
    if (storageTemp === '-80C' && storageSection === 'door') {
        alert('-80°C freezers do not have door storage');
        return;
    }

    const data = {
        drug_name: drugName,
        stock_concentration: $('#stockConcentration').val() || null,
        stock_unit: $('#stockUnit').val(),
        storage_temp: storageTemp,
        supplier: $('#supplier').val() || null,
        preparation_date: $('#preparationDate').val() || null,
        notes: $('#notes').val() || null,
        solvents: $('#solvents').val() || null,
        solubility: $('#solubility').val() || null,
        light_sensitive: $('#lightSensitive').val() || null,
        preparation_time: $('#preparationTime').val() || null,
        expiration_time: $('#expirationTime').val() || null,
        sterility: $('#sterility').val() || null,
        lot_number: $('#lotNumber').val() || null,
        product_number: $('#productNumber').val() || null,
        storage_section: storageSection || null,
        storage_row: $('#storageRow').val() || null,
        storage_column: $('#storageColumn').val() || null
    };

    const url = currentEditingId ? `/api/record/${currentEditingId}` : '/api/record';
    const method = currentEditingId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            $('#recordModal').modal('hide');
            loadRecords();
            loadFridgeDisplays();
            alert(currentEditingId ? 'Record updated successfully' : 'Record added successfully');
        } else {
            alert('Error: ' + (result.error || 'Failed to save record'));
        }
    })
    .catch(error => {
        console.error('Error saving record:', error);
        alert('Failed to save record');
    });
}

// Delete record
function deleteRecord(id) {
    if (!confirm('Are you sure you want to delete this record?')) {
        return;
    }

    fetch(`/api/record/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            loadRecords();
            loadFridgeDisplays();
            alert('Record deleted successfully');
        } else {
            alert('Error: ' + (result.error || 'Failed to delete record'));
        }
    })
    .catch(error => {
        console.error('Error deleting record:', error);
        alert('Failed to delete record');
    });
}

// Refresh records
function refreshRecords() {
    loadRecords();
    loadFridgeDisplays();
}

// Update storage section options based on temperature
function updateStorageSectionOptions() {
    const temp = $('#storageTemp').val();
    const section = $('#storageSection');

    if (temp === '-80C') {
        // Disable door option for -80C
        section.html(`
            <option value="">Not Specified</option>
            <option value="body">Body</option>
        `);
    } else {
        section.html(`
            <option value="">Not Specified</option>
            <option value="body">Body</option>
            <option value="door">Door</option>
        `);
    }
}

// Load and display fridge grids
function loadFridgeDisplays() {
    const container = $('#fridgeDisplays');
    container.empty();

    const fridges = [
        {key: '4C', name: '4°C Fridge', color: '#e3f2fd'},
        {key: '-20C', name: '-20°C Freezer', color: '#fff3e0'},
        {key: '-80C', name: '-80°C Ultra-Low Freezer', color: '#fce4ec'}
    ];

    fridges.forEach(fridge => {
        fetch(`/api/fridge/grid/${fridge.key}`)
            .then(response => response.json())
            .then(data => {
                if (data.config) {
                    createFridgeGrid(container, fridge, data.config, data.grid_data);
                }
            })
            .catch(error => {
                console.error(`Error loading fridge ${fridge.key}:`, error);
            });
    });
}

// Create fridge grid visualization
function createFridgeGrid(container, fridge, config, gridData) {
    const fridgeDiv = $('<div class="fridge-section mb-4"></div>');
    fridgeDiv.css('background-color', fridge.color);

    const title = $(`<h5>${fridge.name}</h5>`);
    fridgeDiv.append(title);

    // Create body section
    const bodyDiv = $('<div class="mb-3"></div>');
    bodyDiv.append('<h6>Body</h6>');
    const bodyGrid = createGridSection(fridge.key, 'body', config.body_rows, config.body_columns, gridData);
    bodyDiv.append(bodyGrid);
    fridgeDiv.append(bodyDiv);

    // Create door section (not for -80C)
    if (fridge.key !== '-80C' && config.door_rows > 0 && config.door_columns > 0) {
        const doorDiv = $('<div></div>');
        doorDiv.append('<h6>Door</h6>');
        const doorGrid = createGridSection(fridge.key, 'door', config.door_rows, config.door_columns, gridData);
        doorDiv.append(doorGrid);
        fridgeDiv.append(doorDiv);
    }

    container.append(fridgeDiv);
}

// Create grid section (body or door)
function createGridSection(tempKey, section, rows, cols, gridData) {
    const gridDiv = $('<div class="fridge-grid"></div>');

    for (let row = 0; row < rows; row++) {
        const rowDiv = $('<div class="grid-row"></div>');

        for (let col = 0; col < cols; col++) {
            const key = `${section}-${row}-${col}`;
            const count = gridData[key] || 0;

            let cellClass = 'grid-cell empty';
            let cellText = `${section[0].toUpperCase()}${row}${col}`;

            if (count === 1) {
                cellClass = 'grid-cell single';
                cellText = `${section[0].toUpperCase()}${row}${col}<br><small>(1 item)</small>`;
            } else if (count > 1) {
                cellClass = 'grid-cell multiple';
                cellText = `${section[0].toUpperCase()}${row}${col}<br><small>(${count} items)</small>`;
            }

            const cell = $(`<div class="${cellClass}">${cellText}</div>`);
            cell.on('click', function() {
                showLocationItems(tempKey, section, row, col);
            });

            rowDiv.append(cell);
        }

        gridDiv.append(rowDiv);
    }

    return gridDiv;
}

// Show items at a specific location
function showLocationItems(tempKey, section, row, col) {
    fetch(`/api/location/${tempKey}/${section}/${row}/${col}`)
        .then(response => response.json())
        .then(records => {
            const modalTitle = $('#locationModalTitle');
            const modalBody = $('#locationItemsList');

            modalTitle.text(`Items at ${tempKey} - ${section.charAt(0).toUpperCase() + section.slice(1)}: Row ${row}, Column ${col}`);
            modalBody.empty();

            if (records.length === 0) {
                modalBody.html('<p class="text-muted">No items at this location</p>');
            } else {
                const list = $('<ul class="list-group"></ul>');
                records.forEach(record => {
                    const item = $(`
                        <li class="list-group-item">
                            <strong>${record.drug_name}</strong><br>
                            <small>
                                Concentration: ${record.stock_concentration || '-'} ${record.stock_unit || ''}<br>
                                Supplier: ${record.supplier || '-'}<br>
                                Prep Date: ${record.preparation_date || '-'}
                            </small><br>
                            <button class="btn btn-sm btn-primary mt-2" onclick="editRecord(${record.id}); $('#locationModal').modal('hide');">
                                <i class="bi bi-pencil"></i> Edit
                            </button>
                        </li>
                    `);
                    list.append(item);
                });
                modalBody.append(list);
            }

            $('#locationModal').modal('show');
        })
        .catch(error => {
            console.error('Error loading location items:', error);
            alert('Failed to load items at this location');
        });
}
