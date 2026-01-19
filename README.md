# Lab Management System - Web Interface

A modern web-based laboratory inventory management system built with Flask, featuring:
- Complete drug/reagent inventory tracking
- Visual fridge storage with customizable grid layouts
- Dilution and concentration calculators
- Real-time search and filtering
- CSV export functionality

## Features

### 1. Inventory Management
- Add, edit, and delete inventory records
- Track stock concentrations, suppliers, lot numbers, and more
- Real-time search by name, supplier, or notes
- Filter by storage temperature
- Comprehensive field tracking:
  - Drug name, concentration, and unit
  - Storage temperature and location
  - Supplier and product information
  - Preparation and expiration dates
  - Sterility and light sensitivity
  - Solvents and solubility information

### 2. Visual Fridge Storage
- Interactive grid visualization for 3 temperature zones:
  - 4°C Fridge (body + door sections)
  - -20°C Freezer (body + door sections)
  - -80°C Ultra-Low Freezer (body only, no door)
- Customizable grid layouts (rows and columns)
- Color-coded cells:
  - White = Empty
  - Light Green = Single item
  - Light Pink = Multiple items
- Click on cells to view items at that location
- Assign storage locations when adding/editing records

### 3. Calculator Tools

#### Dilution Calculator
- Calculate volumes for preparing dilutions using C₁V₁ = C₂V₂
- Select components from inventory or enter manually
- Large, readable results display
- Formatted calculation breakdown

#### Actual Concentration Calculator
- Calculate final concentrations when adding multiple components to media
- Add multiple components with different stock concentrations
- Supports µL and mL volume units
- Automatic final concentration calculations for each component

### 4. Fridge Configuration
- Customize grid layout for each fridge
- Set number of rows and columns for body and door sections
- Changes apply immediately
- Validation prevents door storage for -80°C freezers

### 5. Data Export
- Export entire inventory to CSV format
- Timestamped filenames
- All fields included

## System Requirements

- Python 3.7 or higher
- Modern web browser (Chrome, Firefox, Edge, Safari)
- Windows, macOS, or Linux

## Installation

1. **Install Python** (if not already installed)
   - Download from https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

2. **Install Required Packages**

   Open Command Prompt or Terminal and navigate to the application folder:
   ```bash
   cd D:\lab_management_web
   ```

   Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. **Start the Server**

   In the application folder, run:
   ```bash
   python app.py
   ```

   You should see:
   ```
   ================================================================================
   Lab Management System - Web Interface
   ================================================================================
   Server starting on http://localhost:5000
   Press Ctrl+C to stop the server
   ================================================================================
   ```

2. **Open in Browser**

   Open your web browser and go to:
   ```
   http://localhost:5000
   ```

3. **Stop the Server**

   Press `Ctrl+C` in the terminal/command prompt window

## Usage Guide

### Managing Records

#### Adding a New Record
1. Click "Add New Record" button on the home page
2. Fill in the required fields (drug name is mandatory)
3. Optionally assign a storage location:
   - Select section (body or door)
   - Enter row and column numbers
4. Click "Save Record"

#### Editing a Record
1. Click the pencil icon next to the record in the table
2. Modify the fields as needed
3. Click "Save Record"

#### Deleting a Record
1. Click the trash icon next to the record
2. Confirm the deletion

#### Searching and Filtering
- Use the search box to find records by name, supplier, or notes
- Use the temperature dropdown to filter by storage temperature
- Click "Refresh" to reload all records

### Using the Fridge Display

#### Viewing Storage
- The right panel shows visual grids for all three fridges
- Cell colors indicate occupancy:
  - White = Empty
  - Light Green = 1 item stored
  - Light Pink = Multiple items stored
- Cell labels show section and position (e.g., "B00" = Body Row 0, Column 0)

#### Viewing Items at a Location
- Click any grid cell to see items stored at that location
- A popup will show all records at that position
- Click "Edit" on any item to modify its details

### Using the Calculators

#### Dilution Calculator
1. Click "Calculators" → "Dilution Calculator" in the navigation menu
2. Optionally select a component from your inventory
3. Or manually enter:
   - Stock concentration (C₁) and unit
   - Desired final concentration (C₂) and unit
   - Desired final volume (V₂) in mL
4. Click "Calculate"
5. Results show:
   - Volume of stock solution needed
   - Volume of solvent to add
   - Preparation instructions

#### Actual Concentration Calculator
1. Click "Calculators" → "Actual Concentration Calculator"
2. Enter the initial media volume (mL)
3. Click "Add Component" to add each component
4. For each component:
   - Select from inventory or enter manually
   - Enter stock concentration and unit
   - Enter volume added (µL or mL)
5. Click "Calculate Actual Concentrations"
6. Results show final concentration for each component

### Configuring Fridges

1. Click "Configure Fridges" in the navigation menu
2. For each fridge, set:
   - Body section rows and columns (1-10)
   - Door section rows and columns (1-10, not available for -80°C)
3. Click "Save Configuration"
4. Changes apply immediately
5. Return to home page to see the updated grid layout

### Exporting Data

1. Click "Export CSV" in the navigation menu
2. Your browser will download a CSV file named `lab_inventory_YYYYMMDD_HHMMSS.csv`
3. Open in Excel, Google Sheets, or any spreadsheet application

## File Structure

```
lab_management_web/
├── app.py                      # Main Flask application
├── database.py                 # Database operations
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── lab_management.db           # SQLite database (auto-created)
├── templates/                  # HTML templates
│   ├── base.html              # Base template with navigation
│   ├── index.html             # Main inventory page
│   ├── config.html            # Fridge configuration page
│   ├── dilution_calculator.html
│   └── actual_concentration_calculator.html
└── static/                     # Static files
    ├── css/                    # Custom CSS (if any)
    └── js/
        └── main.js            # JavaScript for interactivity
```

## Database

The application uses SQLite with two main tables:

### `drugs` Table
Stores all inventory records with fields:
- id, drug_name, stock_concentration, stock_unit
- storage_temp, supplier, preparation_date
- notes, solvents, solubility, light_sensitive
- preparation_time, expiration_time, sterility
- lot_number, product_number
- storage_section, storage_row, storage_column

### `fridge_config` Table
Stores grid configuration for each temperature:
- temp_key (4C, -20C, -80C)
- body_rows, body_columns
- door_rows, door_columns

## Troubleshooting

### Server Won't Start

**Error: "Address already in use"**
- Another application is using port 5000
- Solution: Stop the other application or change the port in `app.py` (last line)

**Error: "No module named 'flask'"**
- Flask is not installed
- Solution: Run `pip install -r requirements.txt`

### Database Issues

**Error: "Database is locked"**
- Another process is accessing the database
- Solution: Close any other instances of the application

**Missing data after migration**
- The database file might not have been copied
- Solution: Copy `lab_management.db` from the original folder to `D:\lab_management_web\`

### Browser Issues

**Page not loading**
- Check that the server is running in the terminal
- Try a different browser
- Clear browser cache

**Features not working**
- Ensure JavaScript is enabled in your browser
- Check browser console for errors (F12)

## Migrating Data from Desktop Application

If you have data in the old desktop application:

1. **Locate the database file**
   - Original location: `D:\lab_management\lab_management.db`

2. **Copy to web application folder**
   ```bash
   copy D:\lab_management\lab_management.db D:\lab_management_web\lab_management.db
   ```

3. **Restart the web application**
   - Stop the server (Ctrl+C)
   - Start again: `python app.py`

Your data will now be available in the web interface!

## Security Notes

- This application runs on **localhost only** - it's not accessible from other computers
- No user authentication is implemented - anyone with access to your computer can use it
- For production use in a shared environment, consider adding authentication
- The database file contains all your data - keep backups regularly

## Backup Recommendations

1. **Regular Backups**
   - Copy `lab_management.db` to a backup location regularly
   - Use cloud storage (Google Drive, Dropbox) for automatic backups

2. **Export CSV**
   - Periodically export your inventory to CSV as a backup
   - CSV files can be opened in any spreadsheet application

3. **Automatic Backup Script** (Optional)
   - Create a batch file to copy the database to a backup folder
   - Schedule it to run daily using Windows Task Scheduler

## Support and Development

### Original Desktop Application
- Backup location: `D:\lab_management_backup_20260116_204349\`
- Contains: `lab_manager.py`, `README.txt`, database, and config files

### Web Application
- Current location: `D:\lab_management_web\`
- Built with Flask and Bootstrap 5
- Responsive design works on tablets and mobile devices

## Version History

### Web Version 1.0 (2026-01-16)
- Initial web-based interface
- Complete feature parity with desktop application
- Responsive Bootstrap 5 UI
- Real-time interactive fridge grids
- Enhanced calculator interfaces
- CSV export functionality

### Desktop Version (Legacy)
- Original tkinter-based application
- All features migrated to web version
- Backup preserved for reference

## License

This is a custom application developed for laboratory inventory management.
Not licensed for redistribution or commercial use.

---

**Lab Management System Web Interface**
Version 1.0 - January 2026
