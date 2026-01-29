# Visual Fridge Layout System - User Guide

## Overview

Your Lab Management System now has a **photo-based visual fridge layout system**! This system allows you to:

- Upload actual photos of your fridges
- Draw clickable regions directly on the photos
- Click regions to view or assign inventory items
- See at-a-glance which areas are full or empty
- Migrate items from the old row/column system

The visual system works **alongside** your existing row/column system - you can use both methods.

---

## Quick Start

### 1. Set Up Visual Layouts (One-Time Setup)

1. **Start the Flask application:**
   ```bash
   cd "D:\Lab Management"
   python app.py
   ```

2. **Open your browser** to `http://localhost:5000`

3. **Navigate to:** Configure → Visual Layout Builder

4. **For each fridge section you want to visualize:**
   - Select Temperature (4C, -20C, or -80C)
   - Select Section (Body or Door)
   - Choose photo file (your fridge photos are at: `D:\Lab Management\-20_fridge_body.jpeg` and `D:\Lab Management\-20_fridge_door.jpeg`)
   - Click "Upload Photo"

5. **Draw regions on the photo:**
   - Enter a descriptive name (e.g., "Shelf 1 - Left", "Door Bin 1")
   - Click "Start Drawing"
   - Click and drag on the photo to create a rectangular region
   - Click "Save Region"
   - Repeat for all storage areas in that section

6. **Repeat for other fridge sections** (other temperatures, door sections)

---

## Main Features

### Visual Layout Builder
**Location:** Configure → Visual Layout Builder

**Purpose:** Create and manage photo-based fridge layouts

**How to use:**

1. **Upload a Fridge Photo**
   - Select temperature and section
   - Choose your photo file
   - Click "Upload Photo"

2. **Define Storage Regions**
   - Enter a region name (e.g., "Top Shelf - Left", "Door Bin 3")
   - Click "Start Drawing"
   - Click and drag on the photo to outline the storage area
   - Click "Save Region"

3. **Manage Regions**
   - View all defined regions in the right panel
   - Delete regions with the trash icon
   - Regions are saved automatically

**Tips:**
- Use descriptive names that match your actual fridge layout
- Draw regions to match physical compartments (shelves, bins, drawers)
- You can overlap regions if needed
- Delete and redraw if you make a mistake

---

### Visual Fridge Display
**Location:** Visual Fridge in the navigation menu

**Purpose:** View your fridges with photo-based layouts and manage item locations

**Features:**

1. **Color-Coded Regions**
   - **Blue** = Empty (no items)
   - **Green** = Occupied (1-3 items)
   - **Red** = Crowded (4+ items)

2. **Item Count Badges**
   - Numbers show how many items are in each region
   - Empty regions show no number

3. **Interactive Regions**
   - Click any region to see items stored there
   - Assign new items to the region
   - Remove items from the region

**How to use:**

1. **View Items in a Region**
   - Click on any colored region
   - A modal shows all items stored there
   - Each item shows: name, concentration, supplier, lot number, notes

2. **Assign Items to a Region**
   - Click on a region
   - Click "Assign Item to This Region"
   - Select an item from the dropdown
   - Click "Assign"

3. **Remove Items from a Region**
   - Click on a region
   - Click the X button next to any item
   - Confirm removal

---

### Location Migration Tool
**Location:** Configure → Location Migration Tool

**Purpose:** Convert items from old row/column system to new visual regions

**When to use:**
- After setting up visual layouts
- When you have existing items with row/column locations
- To bulk-assign items based on their old location

**How to use:**

1. **Select a Temperature**
   - Choose 4C, -20C, or -80C from the dropdown
   - Items with row/column locations will be grouped

2. **Select Items to Migrate**
   - Items are grouped by their location (e.g., "Body - Row 0, Column 1")
   - Check individual items OR click "Select All" for a group
   - Selected items appear in the right panel

3. **Choose Target Region**
   - Select a visual region from the dropdown
   - Must match the temperature of selected items

4. **Migrate**
   - Click "Migrate to Region"
   - Confirm the migration
   - Items will be assigned to the visual region

5. **Monitor Progress**
   - Statistics show:
     - Items with visual regions (migrated)
     - Items with row/column only (need migration)
     - Items without any location

**Tips:**
- Migrate one temperature at a time
- Use the group "Select All" button for efficiency
- Check the visual display after migration to verify
- You can re-assign items anytime

---

## Workflow Example: -20C Freezer

Your -20C fridge photos are ready at: `D:\Lab Management\`

### Step 1: Upload Body Photo

1. Go to Visual Layout Builder
2. Select:
   - Temperature: **-20C**
   - Section: **Body**
   - Photo: `D:\Lab Management\-20_fridge_body.jpeg`
3. Click "Upload Photo"

### Step 2: Define Body Regions

Based on your photo (foam dividers creating zones):

1. **Region: "Left Zone"**
   - Draw rectangle over the left storage area
   - Save region

2. **Region: "Center Zone"**
   - Draw rectangle over the center storage area
   - Save region

3. **Region: "Right Zone"**
   - Draw rectangle over the right storage area
   - Save region

4. **Region: "Far Right"**
   - Draw rectangle over the far right area
   - Save region

### Step 3: Upload Door Photo

1. Select:
   - Temperature: **-20C**
   - Section: **Door**
   - Photo: `D:\Lab Management\-20_fridge_door.jpeg`
2. Click "Upload Photo"

### Step 4: Define Door Regions

Based on your photo (5 vertical bins):

1. **Region: "Bin 1"** (leftmost)
2. **Region: "Bin 2"**
3. **Region: "Bin 3"** (center)
4. **Region: "Bin 4"**
5. **Region: "Bin 5"** (rightmost)

### Step 5: View Your Work

1. Go to "Visual Fridge" in navigation
2. Scroll to -20C Freezer section
3. You'll see both body and door photos with your defined regions

### Step 6: Migrate Existing Items (Optional)

1. Go to Location Migration Tool
2. Select -20C from dropdown
3. You'll see items grouped by old row/column locations
4. For each group:
   - Select all items in that location
   - Choose corresponding visual region
   - Click "Migrate to Region"

### Step 7: Assign New Items

1. When adding new inventory:
   - Go to Visual Fridge Display
   - Click the region where you'll store the item
   - Click "Assign Item to This Region"
   - Select the item from the list

---

## Database Schema

The system uses three new tables:

### `fridge_layouts`
Stores uploaded photos for each fridge section

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| temp_key | TEXT | Temperature (4C, -20C, -80C) |
| section | TEXT | Section (body, door) |
| photo_filename | TEXT | Uploaded photo filename |
| created_at | TEXT | Creation timestamp |
| updated_at | TEXT | Last update timestamp |

### `fridge_regions`
Stores defined regions on photos

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| layout_id | INTEGER | Links to fridge_layouts |
| region_name | TEXT | User-defined name |
| x, y | INTEGER | Top-left corner position (pixels) |
| width, height | INTEGER | Region dimensions (pixels) |
| created_at | TEXT | Creation timestamp |

### `drugs` table (updated)
Added new column:

| Column | Type | Description |
|--------|------|-------------|
| fridge_region_id | INTEGER | Links to fridge_regions (optional) |

**Note:** The old `storage_section`, `storage_row`, and `storage_column` fields are still present and functional. Items can have:
- Only visual region assignment
- Only row/column location
- Both (for transition period)
- Neither (unassigned)

---

## API Endpoints

New endpoints for visual layout system:

### Photo Upload
```
POST /api/layout/upload
Form data: photo, temp_key, section
```

### Get Layout
```
GET /api/layout/{temp_key}/{section}
Returns: layout, regions, occupancy
```

### Create Region
```
POST /api/layout/{layout_id}/region
Body: region_name, x, y, width, height
```

### Get Region Items
```
GET /api/region/{region_id}/items
Returns: Array of items in region
```

### Assign Item to Region
```
POST /api/region/{region_id}/assign
Body: drug_id
```

### Delete Region
```
DELETE /api/region/{region_id}
```

---

## Troubleshooting

### "No visual layout configured" message

**Problem:** You haven't created a layout for that temperature/section

**Solution:** Go to Visual Layout Builder and upload a photo with regions

---

### Regions not showing on Visual Display

**Problem:** Database or photo file issues

**Solution:**
1. Check that photo file exists in `D:\Lab Management\static\fridge_photos\`
2. Refresh the page
3. Check browser console for errors (F12)

---

### Can't draw regions

**Problem:** Photo not loaded or JavaScript error

**Solution:**
1. Verify photo uploaded successfully
2. Check file size (max 16MB)
3. Use supported formats: JPG, PNG, GIF
4. Try different browser

---

### Migration not working

**Problem:** No regions defined for that temperature

**Solution:**
1. Go to Visual Layout Builder
2. Create layouts and regions for that temperature
3. Return to Migration Tool
4. Select temperature again to refresh region list

---

### Items not appearing in Visual Display

**Problem:** Items not assigned to visual regions

**Solution:**
- Use Location Migration Tool to bulk-assign items
- OR manually assign items by clicking regions
- Items will show in Visual Display once assigned

---

## File Locations

- **Application Root:** `D:\Lab Management\`
- **Uploaded Photos:** `D:\Lab Management\static\fridge_photos\`
- **Your -20C Photos:**
  - `D:\Lab Management\-20_fridge_body.jpeg`
  - `D:\Lab Management\-20_fridge_door.jpeg`
- **Database:** `D:\Lab Management\lab_management.db`

---

## Tips and Best Practices

### Naming Regions

**Good names:**
- "Top Shelf - Left Side"
- "Door Bin 3"
- "Drawer 1"
- "Back Left Corner"
- "Middle Rack - Position 2"

**Avoid:**
- "Region 1" (not descriptive)
- "R1" (too short)
- "The place where I usually put the samples" (too long)

### Organization Strategies

1. **By Shelf/Level**
   - "Shelf 1 - Left", "Shelf 1 - Right"
   - "Shelf 2 - Left", "Shelf 2 - Right"

2. **By Grid**
   - "A1", "A2", "A3"
   - "B1", "B2", "B3"

3. **By Content Type**
   - "Antibiotics Zone"
   - "Cell Media Area"
   - "Buffers Section"

4. **By Size**
   - "Large Bottles"
   - "Small Vials"
   - "Tubes"

### Photo Guidelines

- **Lighting:** Take photos with good, even lighting
- **Angle:** Straight-on view works best
- **Empty or Full:** Either works, but empty shows layout clearer
- **Resolution:** Higher is better (but under 16MB)
- **Format:** JPG or PNG preferred

### Maintenance

- **Regular Updates:** Re-photograph if fridge layout changes
- **Audit:** Periodically check that visual regions match physical reality
- **Backup:** Export inventory data regularly (Import/Export → Quick Export CSV)

---

## Advanced Features

### Multiple Photos for Same Section

If your fridge section has multiple compartments that need separate photos:

1. Combine them in one photo using image editing software, OR
2. Create logical divisions and photograph each separately
3. Upload the combined/divided photo
4. Draw regions accordingly

### Overlapping Regions

You can draw overlapping regions if needed:

- One item can only be in one region
- But regions can physically overlap on the photo
- Useful for nested storage (box within shelf)

### Region Editing

Currently, to edit a region:

1. Delete the old region
2. Create a new region with correct dimensions
3. Note: Deleting a region unassigns all items in it

---

## System Integration

### With Old Grid System

The visual system **complements** the grid system:

- Old system: Still available, not removed
- New system: Photo-based, more intuitive
- Can use **both**: Items can have both location types
- Migration: Transfer items from old → new at your pace

### With CSV Import/Export

- Export includes both location systems
- Import can specify row/column (old system)
- Visual regions must be assigned through web interface

### With Calculators

- Unchanged: Dilution and Concentration calculators work as before
- Location is cosmetic: Doesn't affect calculations

---

## Future Enhancements (Possible)

Ideas for further development:

1. **Region Editing:** Edit existing regions without deletion
2. **Drag-and-Drop:** Drag items between regions
3. **Heat Maps:** Show usage frequency
4. **Search on Map:** Highlight regions containing search term
5. **Mobile App:** Access visual layouts on tablets
6. **QR Codes:** Generate region QR codes for labels
7. **Multi-Photo Layouts:** Carousel of multiple angles

---

## Getting Help

If you need assistance:

1. Check this guide first
2. Check `README.md` for general system info
3. Check browser console (F12) for error messages
4. Verify file permissions on upload folder
5. Test with a small photo first
6. Try different browser if issues persist

---

## Summary

The Visual Fridge Layout System provides an intuitive way to manage your lab inventory using actual photos of your storage. Key benefits:

✓ Visual, photo-based interface
✓ Click to view/assign items
✓ Color-coded occupancy
✓ Migration tool for existing data
✓ Works alongside traditional system
✓ No coding required

Get started by uploading your -20C fridge photos and defining regions!

---

**Lab Management System - Visual Layout Feature**
Version 1.1 - January 2026
Built with Flask, Canvas API, and Bootstrap 5
