# Lab Management System

Tracks lab reagents and antibodies, where they are stored, and designs
immunofluorescence panels. Flask + SQLite, with a touchscreen display beside
the &minus;80&nbsp;&deg;C freezer.

## Two machines

```
   LAB PC  (authoritative)                 PI  "labfridge"  (replica)
   ┌──────────────────────┐                ┌──────────────────────────┐
   │ lab_management.db    │  sync_to_pi.py │ lab_management.db        │
   │ add and edit here    │ ─────────────▶ │ read-only, refuses writes│
   │ Lab Management.lnk   │  every 5 min   │ 7" touchscreen at the -80│
   └──────────────────────┘    ONE WAY     └──────────────────────────┘
```

All changes happen on the PC. The Pi shows a copy for looking things up and
returns 403 to anything that would write &mdash; a write accepted there would be
destroyed by the next sync, and silent data loss is worse than a refusal.

One-way replication rather than sync is what keeps this simple: the replica
never writes, so there are no id collisions, no conflicts and no delete
tombstones to reconcile.

## Using it

**On the PC**, open **Lab Management** from the Desktop or Start Menu. It starts
the server if needed and opens its own window &mdash; no address bar, one instance
only. Closing the window leaves the server running.

**At the freezer**, the panel boots straight into the touch display. It needs no
interaction to stay current and shows its own address and sync state in the
corner.

### Storage

Storage is a **tree of containers**, not a fixed grid: a unit holds whatever
sections, shelves, racks, drawers and boxes it actually has, nested to whatever
depth exists. Shelves can hold different numbers of racks, a unit can have no
door or several, and a compartment can run at a different temperature from its
appliance.

The &minus;80's racks are a **4&nbsp;&times;&nbsp;4 matrix**: positions number 1&ndash;16
left to right then down, with the door edge on the right. A position exists only
because something is stored there &mdash; putting the last item somewhere creates
it, taking the last one out frees it.

Edit all of this at **Structure** (`/freezer`): click a rack, click a position,
say what is in it. **Edit layout** (`/storage-editor`) adds units, shelves and
racks.

### Filling in a record from the supplier

Paste a product page address and press **Fetch details**. Name, catalogue
number, supplier, description and pack size are filled where the form is blank;
nothing already typed is overwritten.

Some suppliers (Sigma-Aldrich, R&amp;D Systems) refuse this server, and some build
their pages in JavaScript. For those, set up the **Lab Capture** bookmark from
*Import/Export &rarr; Browser capture setup*, click it on the product page, then
press **From browser**. Pasting the page works too.

Concentration is only taken from an explicitly labelled field, never from the
description &mdash; product text is full of potency figures ("IC50 = 140 nM") and
storing one as a stock concentration is a number somebody would dilute from.

### History and undelete

Every change to a record keeps a snapshot. **Import/Export &rarr; History &amp;
undelete** lists recent changes with what changed in each, and puts back
anything deleted, restored to its state at deletion.

This is implemented as SQLite triggers, so every write is recorded &mdash; a CSV
import, the storage tree moving items, or SQL run by hand. `changed_by` records
a network address, not a person; there is no login.

### Antibodies

`/antibodies` manages primaries and secondaries and includes a panel designer
that flags **fluorophore collisions** and **cross-reactivity** (a secondary whose
host species is targeted by another selected secondary).

### Calculators

Dilution (C&#8321;V&#8321;&nbsp;=&nbsp;C&#8322;V&#8322;) with unit conversion, and
actual concentration for several components added to a fixed media volume.

## Backups

Hourly, to three places, by scheduled task:

| | Survives |
|---|---|
| `backups/` | ordinary mistakes |
| `..\LabManagementBackups\` | deleting the project folder |
| OneDrive &rarr; `LabManagement Backups\` | losing the PC |

```bash
python backup_db.py              # all three, prune to 30 copies each
python backup_db.py --to DIR     # somewhere else instead
```

A destination that cannot be written does not stop the others; failures print
even under `--quiet` and exit non-zero, because a backup system that stops
quietly is the failure this exists to prevent. **Restore verified**: a working
system was rebuilt from the OneDrive copy alone.

**The Pi replica is not a backup.** It is overwritten every five minutes, so a
deletion reaches it within minutes.

## Running and deploying

```bash
pip install -r requirements.txt   # runtime, all pure-Python
python serve.py                   # waitress, not the dev server
python -m pytest tests -q
```

Every runtime dependency is pure-Python on purpose: piwheels has no wheels for
Trixie-era Pi OS, so anything compiled would try to build from source on the Pi.

See [deploy/README.md](deploy/README.md) for the Pi: panel wiring, the EDID
workaround, the systemd unit, and the kiosk launcher.

## Layout

```
app.py                  routes
database.py             reagent and antibody records, CSV import/export
storage.py              the container tree
history.py              per-record snapshots and undelete
lookup.py               reading supplier product pages
serve.py                waitress entry point
launch_app.pyw          Windows launcher (single instance, own window)
backup_db.py            backups
sync_to_pi.py           one-way replication to the display
migrate_*.py            one-off migrations, each with a dry run
templates/
  index.html            records + storage overview
  freezer.html          spatial structure editor
  kiosk.html            the touch display (standalone, no Bootstrap)
  storage_editor.html   unit/shelf/rack layout
  antibodies.html       antibody management and panel designer
  history.html          changes and undelete
tests/                  127 tests
```

### Schema

| Table | Holds |
|---|---|
| `storage_units` | appliances |
| `storage_containers` | the tree: self-referencing `parent_id`, position within parent, grid shape |
| `drugs` | reagents; `container_id` is the location |
| `primary_antibodies`, `secondary_antibodies` | antibodies |
| `record_history` | a snapshot per change, written by triggers |
| `settings` | lab name, PI name |

Deletion in the container tree uses explicit recursive SQL rather than
`ON DELETE CASCADE`, because sqlite only honours foreign keys when
`PRAGMA foreign_keys` is on per connection and `database.py` does not set it.

## Known limitations

- **No authentication.** Anyone who can reach the port can read everything, and
  write on the PC instance. Fine on a trusted network; not fine beyond one.
- **No quantity.** The system answers *where is it*, not *how much is left*.
  Counting vials reliably needs hardware and discipline this lab does not have,
  so it is deliberately out of scope.
- **The frontend has no automated tests** beyond page-render and syntax checks.
- **The kiosk covers the &minus;80 only.** Other units are managed on the PC.
