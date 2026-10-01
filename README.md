# Lab Management System

A local web app for tracking lab reagents and antibodies, where they are stored,
and designing immunofluorescence panels. Flask + SQLite + Bootstrap 5.

Built for the Costa Lab (ISMMS).

## What it does

### Storage structure
Storage is a **tree of containers**, not a fixed grid. A unit (fridge, freezer,
ultra-low, LN2, cabinet) contains whatever sections, shelves, racks, drawers,
bins and boxes it actually has, nested to whatever depth the hardware has.

This matters because real appliances are irregular:

- shelves can hold different numbers of racks, including none;
- a unit can have no door storage, or several door compartments;
- a compartment can run at a different temperature from its appliance
  (a &minus;20&nbsp;&deg;C drawer inside a 4&nbsp;&deg;C fridge), and can be owned
  by a different lab.

Edit the structure at **Structure** (`/storage-editor`): add or delete units,
add containers at any level, bulk-add ("4 racks, labelled A&ndash;D"), rename in
place by double-clicking, reorder, or drag a container onto another to reparent.

Two safety properties:

- **Deleting never loses items.** Items inside a deleted container move up to
  its parent; deleting a unit leaves its items *unplaced* rather than deleting
  them. Unplaced items are listed in the editor and on the home page.
- **Reparenting cannot create a cycle.** Moving a shelf into its own rack is
  refused.

### Inventory
The home page lists all reagent records with search and temperature filtering,
alongside a live view of the storage tree with item counts per container. Click
any container to see its contents, grouped by the container each item actually
sits in.

A record's location is any container at any depth &mdash; pick "Shelf 2" when
that is all you know, and refine to a box later.

### Antibodies
`/antibodies` manages primary and secondary antibodies and includes a panel
designer that flags two things people get wrong at the bench:

- **fluorophore collisions** &mdash; two primaries assigned the same fluorophore;
- **cross-reactivity** &mdash; a selected secondary whose host species is itself
  targeted by another selected secondary.

### Calculators
- **Dilution** (C&#8321;V&#8321;&nbsp;=&nbsp;C&#8322;V&#8322;) with unit
  conversion across molar, mass/volume and activity units.
- **Actual concentration** for multiple components added to a fixed media volume.

### Import / export
CSV export includes a `Location` column holding the full container path
(`-80°C Freezer > Body > Shelf 2 > B`). Import resolves that path back to the
same container, so an export/import round trip preserves locations. An unknown
or blank path leaves the item unplaced rather than failing the import.

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

The server currently binds `0.0.0.0:5000` using the Flask development server,
with **no authentication**. That is fine on a trusted machine but is not a
deployment: for shared or always-on use, put it behind a real WSGI server
(waitress/gunicorn) and restrict access.

## Backups

The database is **not** in version control (`*.db` is gitignored). Run:

```bash
python backup_db.py
```

This writes a timestamped copy of the `.db` (via sqlite's backup API, so it is
safe while the app is serving) plus `schema.sql` and per-table CSVs into
`backups/`. The text dumps are tracked, so database *content* is versioned even
though the binary is not. Run it before any migration.

## Layout

```
app.py                     Flask routes
database.py                reagent + antibody records, CSV import/export
storage.py                 the storage container tree (canonical schema + logic)
migrate_containers.py      one-off: flat zones -> container tree
migrate_cleanup.py         one-off: retire the legacy location tables
backup_db.py               backups
templates/
  base.html                nav, settings modal
  index.html               records table + storage overview
  storage_editor.html      structure editor
  antibodies.html          antibody management + panel designer
  dilution_calculator.html
  actual_concentration_calculator.html
  import_export.html
static/js/main.js          home page behaviour
tests/                     pytest suite
```

### Schema

| Table | Holds |
|---|---|
| `storage_units` | appliances: name, kind, room, default temperature |
| `storage_containers` | the tree: self-referencing `parent_id`, kind, label, temperature override, owning lab, position within parent, optional reference photo |
| `drugs` | reagent records; `container_id` is the location |
| `primary_antibodies`, `secondary_antibodies` | antibodies; `container_id` is the location |
| `settings` | lab name, PI name |

Deletion is done with explicit recursive SQL rather than `ON DELETE CASCADE`,
because sqlite only honours foreign keys when `PRAGMA foreign_keys` is `ON` per
connection and `database.py` does not set it.

## Tests

```bash
python -m pytest tests -q
```

Covers the storage tree (irregular layouts, cycle prevention, delete semantics,
bulk labelling, CSV location round-trip), the record and calculator APIs, and
CSV import/export.

## History

Locations were originally a fixed body/door grid per appliance, later a
photo-region system, then a flat list of named zones &mdash; three overlapping
models in the schema at once, with temperature and lab ownership encoded in zone
name strings for want of columns. `migrate_containers.py` consolidated all of it
into the container tree; `migrate_cleanup.py` dropped the legacy tables and
columns. Both scripts default to a dry run that reports what they would change.

The pre-migration state is recoverable from `backups/csv/` in git history, and
each container records the zone it came from in `legacy_zone_id`.
