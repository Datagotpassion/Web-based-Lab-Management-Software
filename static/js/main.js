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
            $('#aliquotVolume').val(record.aliquot_volume || '');
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
        storage_column: $('#storageColumn').val() || null,
        aliquot_volume: $('#aliquotVolume').val() || null
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

// Load and display fridge schematic layouts
function loadFridgeDisplays() {
    const container = $('#fridgeDisplays');
    container.empty();

    const fridges = [
        {key: '4C', name: '4°C Fridge', sections: ['body', 'door'], headerClass: 'temp-header-4c'},
        {key: '-20C', name: '-20°C Freezer', sections: ['body', 'door'], headerClass: 'temp-header-20c'},
        {key: '-80C', name: '-80°C Ultra-Low', sections: ['body'], headerClass: 'temp-header-80c'}
    ];

    fridges.forEach(fridge => {
        const fridgeDiv = $(`
            <div class="fridge-section mb-3" style="background: white; border-radius: 8px; overflow: hidden;">
                <div class="p-2 text-white text-center" style="background: linear-gradient(135deg, ${getGradientColor(fridge.key)});">
                    <strong>${fridge.name}</strong>
                </div>
                <div class="p-2" id="fridge-content-${fridge.key}">
                </div>
            </div>
        `);
        container.append(fridgeDiv);

        // Load each section
        fridge.sections.forEach(section => {
            loadSchematicSection(fridge.key, section);
        });
    });
}

function getGradientColor(tempKey) {
    const colors = {
        '4C': '#3498db, #2980b9',
        '-20C': '#f39c12, #d68910',
        '-80C': '#9b59b6, #8e44ad'
    };
    return colors[tempKey] || '#6c757d, #495057';
}

function loadSchematicSection(tempKey, section) {
    fetch(`/api/schematic/${tempKey}/${section}`)
        .then(response => response.json())
        .then(data => {
            const contentDiv = $(`#fridge-content-${tempKey}`);

            if (data.zones && data.zones.length > 0) {
                renderSchematicZones(contentDiv, tempKey, section, data);
            } else {
                // Show "no layout" message only if no zones exist for this section
                if (contentDiv.find(`.section-${section}`).length === 0) {
                    contentDiv.append(`
                        <div class="section-${section} mb-2">
                            <small class="text-muted">${section.charAt(0).toUpperCase() + section.slice(1)}: </small>
                            <a href="/schematic-layout-builder" class="text-primary small">Configure layout</a>
                        </div>
                    `);
                }
            }
        })
        .catch(error => {
            console.error(`Error loading schematic ${tempKey}/${section}:`, error);
        });
}

function renderSchematicZones(contentDiv, tempKey, section, data) {
    // Create occupancy map
    const occupancyMap = {};
    if (data.occupancy) {
        data.occupancy.forEach(occ => {
            occupancyMap[occ.id] = occ.item_count;
        });
    }

    // Group zones by row
    const rowMap = {};
    data.zones.forEach(zone => {
        if (!rowMap[zone.row_index]) {
            rowMap[zone.row_index] = [];
        }
        rowMap[zone.row_index].push({
            ...zone,
            itemCount: occupancyMap[zone.id] || 0
        });
    });

    // Build section HTML
    const sectionDiv = $(`<div class="section-${section} mb-2"></div>`);
    sectionDiv.append(`<small class="text-muted d-block mb-1">${section.charAt(0).toUpperCase() + section.slice(1)}:</small>`);

    const zonesContainer = $('<div style="display: flex; flex-direction: column; gap: 3px;"></div>');

    Object.keys(rowMap).sort((a, b) => a - b).forEach(rowIdx => {
        const zones = rowMap[rowIdx].sort((a, b) => a.col_index - b.col_index);
        const rowDiv = $('<div style="display: flex; gap: 3px;"></div>');

        zones.forEach(zone => {
            const itemCount = zone.itemCount;
            let borderColor = '#bdc3c7';
            let countColor = '#95a5a6';

            if (itemCount > 0) {
                borderColor = '#27ae60';
                countColor = '#27ae60';
            }
            if (itemCount > 3) {
                borderColor = '#e74c3c';
                countColor = '#e74c3c';
            }

            const displayCount = itemCount > 0 ? itemCount : '-';

            const zoneCell = $(`
                <div class="zone-cell-home" style="
                    flex: 1;
                    padding: 5px 8px;
                    border: 2px solid ${borderColor};
                    border-radius: 5px;
                    background-color: ${zone.color || '#f8f9fa'};
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.2s;
                    min-width: 60px;
                " data-zone-id="${zone.id}" data-zone-name="${zone.zone_name}">
                    <div style="font-size: 0.75rem; font-weight: 600;">${zone.zone_name}</div>
                    <div style="font-size: 0.9rem; font-weight: bold; color: ${countColor};">${displayCount}</div>
                </div>
            `);

            zoneCell.on('click', function() {
                showZoneItems(zone.id, zone.zone_name);
            });

            zoneCell.hover(
                function() { $(this).css({'transform': 'translateY(-2px)', 'box-shadow': '0 3px 6px rgba(0,0,0,0.15)'}); },
                function() { $(this).css({'transform': 'none', 'box-shadow': 'none'}); }
            );

            rowDiv.append(zoneCell);
        });

        zonesContainer.append(rowDiv);
    });

    sectionDiv.append(zonesContainer);
    contentDiv.append(sectionDiv);
}

// Show items in a schematic zone
function showZoneItems(zoneId, zoneName) {
    fetch(`/api/schematic/zone/${zoneId}/items`)
        .then(response => response.json())
        .then(items => {
            const modalTitle = $('#locationModalTitle');
            const modalBody = $('#locationItemsList');

            modalTitle.text(`Items in: ${zoneName}`);
            modalBody.empty();

            if (items.length === 0) {
                modalBody.html('<p class="text-muted">No items in this zone</p>');
            } else {
                const list = $('<ul class="list-group"></ul>');
                items.forEach(item => {
                    const listItem = $(`
                        <li class="list-group-item">
                            <strong>${item.drug_name}</strong><br>
                            <small>
                                Concentration: ${item.stock_concentration || '-'} ${item.stock_unit || ''}<br>
                                Supplier: ${item.supplier || '-'}<br>
                                ${item.aliquot_volume ? `Aliquot: ${item.aliquot_volume}<br>` : ''}
                                Prep Date: ${item.preparation_date || '-'}
                            </small><br>
                            <button class="btn btn-sm btn-primary mt-2" onclick="editRecord(${item.id}); $('#locationModal').modal('hide');">
                                <i class="bi bi-pencil"></i> Edit
                            </button>
                        </li>
                    `);
                    list.append(listItem);
                });
                modalBody.append(list);
            }

            $('#locationModal').modal('show');
        })
        .catch(error => {
            console.error('Error loading zone items:', error);
            alert('Failed to load items');
        });
}
