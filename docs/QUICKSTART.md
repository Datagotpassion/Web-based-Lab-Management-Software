# Quick start

Getting from nothing to a working installation. Roughly ten minutes for the
PC, an hour for the freezer display if you want one.

[中文版本](QUICKSTART.zh.md)

---

## 1. The lab PC

### What you need

- Windows 10 or 11
- [Python 3.9 or newer](https://www.python.org/downloads/) &mdash; tick
  **"Add Python to PATH"** during installation
- [Git](https://git-scm.com/download/win), or download the repository as a ZIP

### Install

```powershell
git clone <repository-url> "D:\Lab Management"
cd "D:\Lab Management"
.\setup_windows.ps1 -WithExamples
```

If PowerShell refuses to run the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -WithExamples
```

That creates a virtual environment, installs dependencies, builds a database,
adds **Lab Management** to your Desktop and Start Menu, and registers an hourly
backup.

`-WithExamples` fills it with invented contents so there is something to look
at. **Delete `lab_management.db` and re-run without the flag** when you are
ready to enter real data.

### Open it

Double-click **Lab Management**. It starts the server and opens its own window.
Only one window opens however many times you click.

---

## 2. First five minutes in the app

The order matters: describe your storage first, then put things in it.

### Describe a freezer

**Structure** in the menu &rarr; **Edit layout**.

1. **Add Unit** &mdash; name it, choose a kind, set its usual temperature.
   Leave the temperature blank for a combined fridge/freezer and set it per
   section instead.
2. Add a **section** inside it (Body, Door &mdash; whatever it really has).
3. Add **shelves** inside the section. Hover a container and press **+**; set
   a count above 1 to add several at once.
4. Add **racks** inside a shelf the same way.

Nothing is forced to be uniform. A shelf may hold three racks while the next
holds five, a unit may have no door or three doors, and a compartment can run
at its own temperature.

### Say what a rack holds

**Structure** &rarr; click a rack. If it is a grid of boxes, set its shape in
**Edit layout** &rarr; properties (the &minus;80 here is 4 columns &times; 4 rows).

Click a **position** and tick what is stored there. A position exists only
while something is in it: filling an empty slot creates it, emptying it frees
it. Positions are numbered left to right then down, with the door edge on the
right.

### Add a reagent

**Home** &rarr; **Add New Record**.

Paste the supplier's product page address and press **Fetch details** &mdash;
name, catalogue number, supplier, description and pack size are filled in
where the form is blank. Nothing you have already typed is overwritten.

Some suppliers refuse this, or build their pages in JavaScript. For those, set
up the **Lab Capture** bookmark once (*Import/Export &rarr; Browser capture
setup*), click it while viewing the product page, then press **From browser**.

---

## 3. Undoing a mistake

**Import/Export &rarr; History & undelete.**

Every change to a record is kept. The left panel lists anything deleted, with
**Put back** to restore it exactly as it was when deleted. The right panel
shows recent changes and which fields each one altered.

---

## 4. Backups

Set up automatically, hourly, to three places:

| Where | Survives |
|---|---|
| `backups\` inside the project | an ordinary mistake |
| `..\LabManagementBackups\` | deleting the project folder |
| OneDrive (or Google Drive) | losing the PC |

Run one by hand any time:

```powershell
.\venv\Scripts\python.exe backup_db.py
```

To restore: copy a `lab_management_*.db` back over `lab_management.db` and
reopen the app.

> A freezer display is **not** a backup. It is overwritten every few minutes,
> so a deletion reaches it almost immediately.

---

## 5. The freezer display (optional)

A Raspberry Pi with a touchscreen beside the freezer, showing where things are.
It is read-only: all editing stays on the PC.

### Hardware

- Raspberry Pi 4 (2 GB or more). A Pi 3B works; a Pi Zero does not have the
  memory for the browser.
- A 7&Prime; 1024&times;600 HDMI touchscreen, **with its own power supply**
- An Ethernet or Wi-Fi connection

### Wiring

```
        7" panel                                 Raspberry Pi
   +------------------+
   |  HDMI  ----------+----------------------->  HDMI0
   |  TOUCH ----------+----------------------->  any USB port
   |  POWER <---------+--- its own 5V supply
   +------------------+                          Pi <-- its own supply
```

Power the panel separately. It will light up from the TOUCH port alone, which
draws its current through the Pi and causes failures that look like faults
elsewhere.

### Software

On the PC, re-run setup naming the display:

```powershell
.\setup_windows.ps1 -DisplayHost labfridge.local -DisplayUser labuser
```

It prints the two commands to run on the Pi. Then see
[deploy/README.md](../deploy/README.md) for the screen mode, which is the one
part that usually needs attention: these panels often report no EDID, and the
fix is a `video=` line in `cmdline.txt`.

---

## 6. Everyday use

| | |
|---|---|
| Add or change anything | the PC |
| Look something up at the freezer | the panel |
| Changes reach the panel | within 5 minutes, automatically |
| Language | the globe icon in the menu, or **EN/中文** on the panel |

---

## If something is wrong

**The app will not open.** Check Python is installed (`python --version`) and
re-run `setup_windows.ps1`; it is safe to run again.

**The panel shows old data.** Its corner shows its address and sync state. If
it says *not synced*, check from the PC:

```powershell
.\venv\Scripts\python.exe sync_to_pi.py --status
```

**The panel moved and its address changed.** Read the new address off the
panel's own home screen and put it in `.sync_state.json`.

**Something was deleted by accident.** *Import/Export &rarr; History &
undelete.*
