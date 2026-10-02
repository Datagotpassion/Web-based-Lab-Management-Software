// Main JavaScript file for Lab Management System

let allRecords = [];
let currentEditingId = null;
let allUnits = [];        // storage units with their nested containers
let containerIndex = {};  // container id -> {label, path, full_path, temp_c, ...}
let containerList = [];   // the same containers, flat and in tree order

// Initialize on page load
$(document).ready(function() {
    loadFridgesAndInitialize();

    // Search functionality
    $('#searchInput').on('input', function() {
        filterRecords();
    });

    $('#tempFilter').on('change', function() {
        filterRecords();
    });

    // Re-rank the location picker when the storage temperature changes, so
    // matching-temperature containers float to the top.
    $('#storageTemp').on('change', function() {
        populateLocationPicker($('#fridgeZone').val());
    });
});

// Load the storage structure first; records and the picker both depend on it.
function loadFridgesAndInitialize() {
    fetch('/api/storage/flat')
        .then(response => response.json())
        .then(data => {
            containerList = data.containers || [];
            containerIndex = {};
            containerList.forEach(ct => { containerIndex[ct.id] = ct; });
            allUnits = [];
            containerList.forEach(ct => {
                if (!allUnits.some(u => u.id === ct.unit_id)) {
                    allUnits.push({id: ct.unit_id, name: ct.unit_name,
                                   temp_c: ct.temp_is_override ? null : ct.temp_c});
                }
            });
            populateTemperatureFilter();
            populateLocationPicker();
            loadRecords();
            loadStructureOverview();
        })
        .catch(error => {
            console.error('Error loading storage structure:', error);
            // Records are still useful without locations resolved.
            loadRecords();
        });
}

// Populate temperature filter dropdown with dynamic fridge temperatures
function populateTemperatureFilter() {
    const tempFilter = $('#tempFilter');
    const storageTemp = $('#storageTemp');

    // Derive the temperature list from what the storage structure actually
    // contains, rather than from a fixed list. drugs.storage_temp stores keys
    // like '-80C', so numeric container temperatures are converted to match.
    const tempTypes = [...new Set(
        containerList
            .filter(ct => ct.temp_c !== null && ct.temp_c !== undefined)
            .map(ct => `${+ct.temp_c}C`)
    )].sort((a, b) => parseFloat(b) - parseFloat(a));

    // Update filter dropdown (if it exists)
    if (tempFilter.length) {
        // Keep whatever is selected: this can run again after the structure
        // changes, and rebuilding the options would otherwise reset the filter.
        const chosen = tempFilter.val();
        let filterOptions = '<option value="">All Temperatures</option>';
        tempTypes.forEach(temp => {
            const label = formatTempLabel(temp);
            filterOptions += `<option value="${temp}">${label}</option>`;
        });
        // Add RT if not already there
        if (!tempTypes.includes('RT')) {
            filterOptions += '<option value="RT">Room Temperature</option>';
        }
        tempFilter.html(filterOptions);
        if (chosen) tempFilter.val(chosen);
    }

    // Update storage temp dropdown in add/edit form (if it exists)
    if (storageTemp.length) {
        let tempOptions = '';
        tempTypes.forEach(temp => {
            const label = formatTempLabel(temp);
            tempOptions += `<option value="${temp}">${label}</option>`;
        });
        // Add RT if not already there
        if (!tempTypes.includes('RT')) {
            tempOptions += '<option value="RT">Room Temperature</option>';
        }
        storageTemp.html(tempOptions);
    }
}

// Format temperature label for display
function formatTempLabel(temp) {
    const labels = {
        '4C': '4°C',
        '-20C': '-20°C',
        '-80C': '-80°C',
        '-150C': '-150°C',
        '-196C': '-196°C',
        'RT': 'Room Temperature'
    };
    return labels[temp] || temp;
}

// Sanitize temp key for use in element IDs (handles special chars like -)
function sanitizeIdKey(tempKey) {
    return tempKey.replace(/-/g, 'm');
}

// Indent an option label so nesting is visible inside a flat <select>.
function containerOptionLabel(ct) {
    const indent = '  '.repeat(ct.depth);
    const bits = [ct.label];
    if (ct.temp_is_override) bits.push(`${+ct.temp_c} °C`);
    if (ct.owner_lab) bits.push(ct.owner_lab);
    if (ct.item_count) bits.push(`${ct.item_count} item${ct.item_count === 1 ? '' : 's'}`);
    return `${indent}${bits.join('  ·  ')}`;
}

// Populate the location picker from the container tree.
//
// Every container is selectable at any depth, so you can say "Shelf 2" when
// that is all you know and refine to a box later. Containers whose temperature
// matches the selected storage temperature are grouped first, but nothing is
// hidden -- a -20 °C compartment inside a 4 °C fridge has to stay reachable.
function populateLocationPicker(selectedId) {
    const picker = $('#fridgeZone');
    const hint = $('#zoneHint');
    if (!picker.length) return;

    if (!containerList.length) {
        picker.html('<option value="">No storage structure defined</option>');
        hint.html('Build your fridges in <a href="/storage-editor">Structure</a>');
        return;
    }

    const temp = $('#storageTemp').val();
    const wanted = temp ? parseFloat(temp) : null;
    const matches = ct => wanted !== null && ct.temp_c !== null
                          && Math.abs(+ct.temp_c - wanted) < 0.001;

    let options = '<option value="">No location set</option>';

    const groupFor = (unitId, list, suffix) => {
        if (!list.length) return '';
        const unitName = list[0].unit_name;
        let html = `<optgroup label="${escapeHtml(unitName)}${suffix}">`;
        list.forEach(ct => {
            html += `<option value="${ct.id}">`
                  + `${escapeHtml(containerOptionLabel(ct))}</option>`;
        });
        return html + '</optgroup>';
    };

    const unitIds = [...new Set(containerList.map(ct => ct.unit_id))];

    // Matching temperature first.
    if (wanted !== null) {
        unitIds.forEach(uid => {
            options += groupFor(uid,
                containerList.filter(ct => ct.unit_id === uid && matches(ct)),
                ` — ${formatTempLabel(temp)}`);
        });
    }
    // Then everything else.
    unitIds.forEach(uid => {
        options += groupFor(uid,
            containerList.filter(ct => ct.unit_id === uid && !matches(ct)),
            wanted !== null ? ' — other temperatures' : '');
    });

    picker.html(options);
    if (selectedId) picker.val(String(selectedId));
    hint.html('Pick any level — a shelf, a rack, or a box. '
            + 'Manage the structure in <a href="/storage-editor">Structure</a>.');
}

function escapeHtml(s) {
    return $('<div>').text(s == null ? '' : s).html();
}

// Load all records
function loadRecords() {
    return fetch('/api/records')
        .then(response => response.json())
        .then(records => {
            allRecords = records;
            // Re-apply whatever the search box and temperature filter are set
            // to. Showing the full list here would silently undo a filter the
            // user is still looking at, every time they save or delete.
            filterRecords();
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

    // Reset select all checkbox
    $('#selectAllRecords').prop('checked', false);
    updateSelectedCount();

    if (records.length === 0) {
        tbody.append('<tr><td colspan="8" class="text-center text-muted">No records found</td></tr>');
        return;
    }

    records.forEach(record => {
        const tempBadge = getTempBadge(record.storage_temp);
        const location = getLocationDisplay(record);

        const escapedName = record.drug_name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const row = `
            <tr>
                <td>
                    <input type="checkbox" class="form-check-input record-checkbox" data-id="${record.id}" data-name="${escapedName}" onchange="updateSelectedCount()">
                </td>
                <td>${record.id}</td>
                <td><strong>${record.drug_name}</strong></td>
                <td>${record.stock_concentration || '-'} ${record.stock_unit || ''}</td>
                <td>${tempBadge}</td>
                <td>${location}</td>
                <td>${record.supplier || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="editRecord(${record.id})" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRecord(${record.id}, '${escapedName}')" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

// Toggle select all records
function toggleSelectAllRecords() {
    const isChecked = $('#selectAllRecords').is(':checked');
    $('.record-checkbox').prop('checked', isChecked);
    updateSelectedCount();
}

// Update selected count and show/hide delete button
function updateSelectedCount() {
    const count = $('.record-checkbox:checked').length;
    $('#selectedCount').text(count);
    if (count > 0) {
        $('#deleteSelectedBtn').removeClass('d-none');
    } else {
        $('#deleteSelectedBtn').addClass('d-none');
    }

    // Update select all checkbox state
    const totalCheckboxes = $('.record-checkbox').length;
    if (totalCheckboxes > 0 && count === totalCheckboxes) {
        $('#selectAllRecords').prop('checked', true);
    } else {
        $('#selectAllRecords').prop('checked', false);
    }
}

// Delete selected records
function deleteSelectedRecords() {
    const selected = $('.record-checkbox:checked');
    const count = selected.length;

    if (count === 0) return;

    // Build list of names for confirmation
    const names = [];
    selected.each(function() {
        names.push($(this).data('name'));
    });

    const nameList = names.length <= 5
        ? names.join(', ')
        : names.slice(0, 5).join(', ') + ` and ${names.length - 5} more`;

    if (!confirm(`Delete ${count} item(s)?\n\n${nameList}\n\nThis action cannot be undone.`)) {
        return;
    }

    // Collect IDs and delete
    const ids = [];
    selected.each(function() {
        ids.push($(this).data('id'));
    });

    // Delete records one by one
    let completed = 0;
    let failed = 0;

    ids.forEach(id => {
        fetch(`/api/record/${id}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(result => {
                if (!result.success) failed++;
                completed++;
                if (completed === ids.length) {
                    finishBulkDelete(count, failed);
                }
            })
            .catch(() => {
                failed++;
                completed++;
                if (completed === ids.length) {
                    finishBulkDelete(count, failed);
                }
            });
    });
}

// Finish bulk delete operation
function finishBulkDelete(total, failed) {
    loadRecords();
    loadStructureOverview();

    const success = total - failed;
    if (failed === 0) {
        showDeleteNotification(`${success} item(s)`);
    } else {
        alert(`Deleted ${success} item(s). Failed to delete ${failed} item(s).`);
    }
}

// Get temperature badge HTML
function getTempBadge(temp) {
    const badges = {
        '4C': '<span class="temp-badge temp-4c">4°C</span>',
        '-20C': '<span class="temp-badge temp-minus20">-20°C</span>',
        '-80C': '<span class="temp-badge temp-minus80">-80°C</span>',
        '-150C': '<span class="badge bg-primary">-150°C</span>',
        '-196C': '<span class="badge bg-dark">-196°C</span>',
        'RT': '<span class="badge bg-secondary">RT</span>'
    };
    return badges[temp] || `<span class="badge bg-secondary">${temp}</span>`;
}

// Get location display string from the container tree.
// Shows the immediate container, with the full path on hover, so a deep
// location stays readable in a narrow table column.
function getLocationDisplay(record) {
    const ct = record.container_id ? containerIndex[record.container_id] : null;
    if (ct) {
        return `<span class="badge bg-info" title="${escapeHtml(ct.full_path)}">`
             + `${escapeHtml(ct.label)}</span>`;
    }
    if (record.container_id) {
        // Points at a container that no longer exists -- surface it rather
        // than rendering a silent dash.
        return '<span class="badge bg-danger" '
             + 'title="Points at a container that no longer exists">unknown</span>';
    }
    return '<span class="text-muted">—</span>';
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
    populateLocationPicker();
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
            $('#aliquotVolume').val(record.aliquot_volume || '');
            $('#notes').val(record.notes || '');

            // The picker is built from the already-loaded container index, so
            // the current location can be selected straight away.
            populateLocationPicker(record.container_id);

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
    const containerId = $('#fridgeZone').val();

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
        container_id: containerId ? parseInt(containerId) : null,
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
            loadStructureOverview();
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
function deleteRecord(id, name) {
    const itemName = name || 'this item';
    if (!confirm(`Delete "${itemName}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    fetch(`/api/record/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            loadRecords();
            loadStructureOverview();
            showDeleteNotification(itemName);
        } else {
            alert('Error: ' + (result.error || 'Failed to delete record'));
        }
    })
    .catch(error => {
        console.error('Error deleting record:', error);
        alert('Failed to delete record');
    });
}

// Show a brief notification after deletion
function showDeleteNotification(itemName) {
    // Create notification element
    const notification = $(`
        <div class="delete-notification" style="
            position: fixed;
            top: 20px;
            right: 20px;
            background: #27ae60;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 9999;
            animation: slideIn 0.3s ease;
        ">
            <i class="bi bi-check-circle"></i> "${itemName}" deleted successfully
        </div>
    `);

    $('body').append(notification);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        notification.fadeOut(300, function() {
            $(this).remove();
        });
    }, 3000);
}

// Refresh records
function refreshRecords() {
    loadRecords();
    loadStructureOverview();
}

// ===================== STORAGE STRUCTURE OVERVIEW =====================
//
// Replaces the old fridge grid/schematic visualisation. That drew a fixed
// body/door grid per appliance, which could not show a shelf with three racks
// or a unit with two door sections. This renders the actual container tree, so
// what you see is whatever the hardware really is.

const OVERVIEW_COLLAPSED = new Set();   // container ids collapsed in the panel
const OVERVIEW_AUTO_DEPTH = 2;          // deeper than this starts collapsed

function loadStructureOverview() {
    const host = $('#structureOverview');
    if (!host.length) return;

    // Always re-read, so counts stay honest after an add, edit or delete.
    fetch('/api/storage/tree')
        .then(r => r.json())
        .then(data => renderStructureOverview(host, data.units || [],
                                              data.unplaced || []))
        .catch(error => {
            console.error('Error loading storage structure:', error);
            host.html('<p class="text-danger small mb-0">'
                    + 'Could not load the storage structure.</p>');
        });
}

function renderStructureOverview(host, units, unplaced) {
    host.empty();

    if (!units.length) {
        host.html('<p class="text-muted text-center mb-2">'
                + 'No storage units yet.</p>'
                + '<div class="text-center"><a class="btn btn-sm btn-primary" '
                + 'href="/storage-editor">Build your fridges</a></div>');
        return;
    }

    units.forEach(unit => {
        const temp = unit.default_temp_c === null
            ? '<span class="text-muted">mixed</span>'
            : (+unit.default_temp_c) + ' &deg;C';
        const room = unit.room ? ' &middot; ' + escapeHtml(unit.room) : '';
        const $card = $('<div class="mb-3">'
            + '<div class="d-flex justify-content-between align-items-baseline '
            + 'border-bottom pb-1 mb-1">'
            + '<div><span class="fw-semibold">' + escapeHtml(unit.name) + '</span> '
            + '<span class="text-muted" style="font-size:.78rem">'
            + temp + room + '</span></div>'
            + '<span class="badge bg-light text-secondary">'
            + unit.item_count + ' item' + (unit.item_count === 1 ? '' : 's')
            + '</span></div><div class="overview-body"></div></div>');

        const $body = $card.find('.overview-body');
        if (!unit.containers.length) {
            $body.html('<div class="text-muted fst-italic" style="font-size:.8rem">'
                     + 'Nothing defined inside yet.</div>');
        } else {
            unit.containers.forEach(ct => $body.append(overviewNode(ct, unit, 0)));
        }
        host.append($card);
    });

    if (unplaced.length) {
        host.append('<div class="alert alert-warning py-2 px-2 mb-0" '
            + 'style="font-size:.8rem"><i class="bi bi-exclamation-triangle"></i> '
            + '<strong>' + unplaced.length + '</strong> item'
            + (unplaced.length === 1 ? '' : 's') + ' with no location. '
            + '<a href="/storage-editor" class="alert-link">Place them</a></div>');
    }
}

function overviewNode(ct, unit, depth) {
    // Deep levels start collapsed so the panel stays scannable, but anything
    // actually holding items is shown regardless.
    if (depth >= OVERVIEW_AUTO_DEPTH && ct.child_count
        && !OVERVIEW_COLLAPSED.has(ct.id) && !ct.item_count) {
        OVERVIEW_COLLAPSED.add(ct.id);
    }
    const collapsed = OVERVIEW_COLLAPSED.has(ct.id);
    const hasKids = ct.child_count > 0;

    const chips = [];
    if (ct.temp_c !== null)
        chips.push('<span class="ov-chip">' + (+ct.temp_c) + ' &deg;C</span>');
    if (ct.owner_lab)
        chips.push('<span class="ov-chip">' + escapeHtml(ct.owner_lab) + '</span>');

    let count = '';
    if (ct.item_count) {
        count = '<span class="badge bg-success-subtle text-success-emphasis ov-count" '
              + 'title="items directly here">' + ct.item_count + '</span>';
    } else if (ct.subtree_item_count) {
        count = '<span class="badge bg-light text-secondary ov-count" '
              + 'title="items further inside">' + ct.subtree_item_count + '</span>';
    }

    const caret = hasKids
        ? (collapsed ? '<i class="bi bi-caret-right-fill"></i>'
                     : '<i class="bi bi-caret-down-fill"></i>')
        : '';

    const kids = (hasKids && !collapsed)
        ? '<div class="ov-children">'
          + ct.children.map(k => overviewNode(k, unit, depth + 1)).join('')
          + '</div>'
        : '';

    return '<div class="ov-node-wrap"><div class="ov-node" data-ov="' + ct.id + '">'
         + '<span class="ov-toggle" data-ov-toggle="' + ct.id + '">' + caret + '</span>'
         + '<span class="ov-label' + (ct.item_count ? ' fw-semibold' : '') + '" '
         + 'data-ov-items="' + ct.id + '" '
         + 'title="' + escapeHtml(ct.kind) + ' - click to see contents">'
         + escapeHtml(ct.label) + '</span>'
         + chips.join('') + count
         + '</div>' + kids + '</div>';
}

// Expand/collapse a branch of the overview.
$(document).on('click', '.ov-toggle', function (e) {
    e.stopPropagation();
    const id = +$(this).data('ov-toggle');
    if (!id) return;
    if (OVERVIEW_COLLAPSED.has(id)) OVERVIEW_COLLAPSED.delete(id);
    else OVERVIEW_COLLAPSED.add(id);
    loadStructureOverview();
});

// Click a container to see what is in it, including everything nested inside.
$(document).on('click', '.ov-label', function () {
    const id = +$(this).data('ov-items');
    fetch('/api/storage/containers/' + id + '/items?deep=1')
        .then(r => r.json())
        .then(data => showContainerItems(data))
        .catch(error => {
            console.error('Error loading container items:', error);
            alert('Failed to load contents');
        });
});

function showContainerItems(data) {
    const path = data.path;
    const where = path.unit.name + ' › '
                + path.containers.map(p => p.label).join(' › ');
    $('#locationModalTitle').text(where);

    if (!data.items.length) {
        $('#locationItemsList').html(
            '<p class="text-muted mb-0">Nothing stored here.</p>');
        $('#locationModal').modal('show');
        return;
    }

    // Group by the container each item actually sits in, so a rack's listing
    // still tells you which box things are in.
    const groups = {};
    data.items.forEach(it => {
        if (!groups[it.container_id]) groups[it.container_id] = [];
        groups[it.container_id].push(it);
    });

    let html = '';
    Object.keys(groups).forEach(cid => {
        const ct = containerIndex[cid];
        const label = ct ? ct.path : 'Unknown container';
        html += '<div class="fw-semibold small text-muted mt-2">'
              + escapeHtml(label) + '</div><ul class="list-unstyled mb-0">';
        groups[cid].forEach(it => {
            const kind = it.table === 'drugs' ? 'reagent'
                       : it.table.replace('_', ' ');
            const edit = it.table === 'drugs'
                ? '<button class="btn btn-sm btn-outline-primary ms-2" '
                  + 'data-edit-record="' + it.id + '">Edit</button>'
                : '';
            html += '<li class="d-flex align-items-center py-1">'
                  + '<span>' + escapeHtml(it.name) + '</span>'
                  + '<span class="badge bg-light text-secondary ms-2" '
                  + 'style="font-size:.68rem">' + escapeHtml(kind) + '</span>'
                  + edit + '</li>';
        });
        html += '</ul>';
    });
    $('#locationItemsList').html(html);
    $('#locationModal').modal('show');
}

// Edit straight from the contents list.
$(document).on('click', '[data-edit-record]', function () {
    const id = +$(this).data('edit-record');
    $('#locationModal').modal('hide');
    editRecord(id);
});
