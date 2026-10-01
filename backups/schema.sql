CREATE TABLE drugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_name TEXT NOT NULL,
                stock_concentration REAL,
                stock_unit TEXT,
                storage_temp TEXT,
                supplier TEXT,
                preparation_date TEXT,
                notes TEXT,
                solvents TEXT,
                solubility TEXT,
                light_sensitive TEXT,
                preparation_time TEXT,
                expiration_time TEXT,
                sterility TEXT,
                lot_number TEXT,
                product_number TEXT,
                storage_section TEXT,
                storage_row INTEGER,
                storage_column INTEGER
            , fridge_region_id INTEGER, aliquot_volume TEXT);

CREATE TABLE fridge_config (
                temp_key TEXT PRIMARY KEY,
                body_rows INTEGER DEFAULT 3,
                body_columns INTEGER DEFAULT 3,
                door_rows INTEGER DEFAULT 2,
                door_columns INTEGER DEFAULT 2
            );

CREATE TABLE fridge_layouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temp_key TEXT NOT NULL,
                section TEXT NOT NULL,
                photo_filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(temp_key, section)
            );

CREATE TABLE fridge_regions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id INTEGER NOT NULL,
                region_name TEXT NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layout_id) REFERENCES fridge_layouts(id) ON DELETE CASCADE
            );

CREATE TABLE fridge_schematic_layouts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        temp_key TEXT NOT NULL,
                        section TEXT NOT NULL,
                        layout_name TEXT,
                        reference_photo TEXT,
                        fridge_id INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(fridge_id, section)
                    );

CREATE TABLE fridge_schematic_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id INTEGER NOT NULL,
                zone_name TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                col_index INTEGER NOT NULL,
                col_span INTEGER DEFAULT 1,
                row_span INTEGER DEFAULT 1,
                color TEXT DEFAULT '#e3f2fd',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layout_id) REFERENCES "fridge_schematic_layouts_old"(id) ON DELETE CASCADE
            );

CREATE TABLE fridges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                temp_type TEXT NOT NULL,
                location TEXT,
                has_door INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE primary_antibodies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_protein TEXT,
                host_species TEXT,
                clonality TEXT,
                isotype TEXT,
                clone_number TEXT,
                supplier TEXT,
                catalog_number TEXT,
                lot_number TEXT,
                applications TEXT,
                fixation_compatibility TEXT,
                dilution_if TEXT,
                dilution_wb TEXT,
                dilution_ihc TEXT,
                storage_temp TEXT,
                stock_concentration TEXT,
                aliquot_volume TEXT,
                validated TEXT,
                notes TEXT,
                fridge_region_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            , is_conjugated INTEGER DEFAULT 0, fluorophore TEXT, fluorophore_excitation TEXT, fluorophore_emission TEXT);

CREATE TABLE secondary_antibodies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target_species TEXT,
                target_isotype TEXT,
                host_species TEXT,
                format TEXT,
                conjugate TEXT,
                fluorophore_excitation TEXT,
                fluorophore_emission TEXT,
                cross_adsorbed TEXT,
                cross_adsorbed_against TEXT,
                supplier TEXT,
                catalog_number TEXT,
                lot_number TEXT,
                applications TEXT,
                dilution_if TEXT,
                dilution_wb TEXT,
                dilution_ihc TEXT,
                storage_temp TEXT,
                stock_concentration TEXT,
                aliquot_volume TEXT,
                notes TEXT,
                fridge_region_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

CREATE TABLE sqlite_sequence(name,seq);
