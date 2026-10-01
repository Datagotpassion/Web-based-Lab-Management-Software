# Deploying to a Raspberry Pi

Two separate things, deliberately kept apart:

1. **The service** — the Pi serves the app on the lab network so it is reachable
   from a phone or any lab machine. Low risk, works on any Pi.
2. **The kiosk** — a 7″ touchscreen next to the −80 running a full-screen
   browser. Needs its own power budget; see the warning below.

Do (1) first and confirm it works before bothering with (2).

---

## Hardware notes

This runs on its own Pi, separate from the PlateScope imaging rig.

The service is small — Flask plus waitress, a single SQLite file, no compiled
dependencies — so any Pi will serve it comfortably. The kiosk is the demanding
half: Chromium full-screen wants more than 1 GB is comfortable with, so a
Pi 4B 2 GB or better is the sensible host.

**Power the 7″ panel from its own supply**, and give the Pi the official
adapter rather than a phone charger. Sharing one supply across Pi and panel is
the usual cause of "random display failures", and on this family of hardware an
undervolted 5 V rail has previously corrupted an SD card.

---

## 1. The service

On the Pi:

```bash
git clone <repo url> ~/LabManagement
cd ~/LabManagement
bash deploy/setup-pi.sh
```

The script creates a venv, installs dependencies, installs and starts a systemd
unit, and curls `/api/health` to prove it came up. It is idempotent — re-run it
after any change to the unit file.

Every runtime dependency is pure-Python on purpose (Flask, Werkzeug, waitress),
so nothing compiles. If a compiled dependency is ever added, recreate the venv
with `--system-site-packages` and `apt install` that dependency instead —
piwheels has no wheels for Trixie-era Pi OS Python and pip will try to build
from source and hang.

### Bring your data across

The database is not in git. From the PC:

```powershell
scp 'D:\Lab Management\lab_management.db' kdcberry@raspberrypi.local:~/LabManagement/
sudo systemctl restart labmanager   # on the Pi
```

Run `python backup_db.py` on the PC first.

### Day-to-day

```bash
# update after pushing from the PC
cd ~/LabManagement && git pull && sudo systemctl restart labmanager

# logs
sudo journalctl -u labmanager -f
```

Check it from the PC without SSH, the same way you check PlateScope:

```powershell
Invoke-RestMethod http://raspberrypi.local:5000/api/health
```

```json
{ "status": "ok", "units": 4, "containers": 64,
  "records": 47, "records_placed": 47, "unplaced_items": 48 }
```

### Access from a phone

`.local` names do not resolve on all phones. Either use the Pi's IP, give it a
DHCP reservation, or — better — put the Pi and your phone on a Tailscale
network and use the Tailscale name. There is **no authentication**, so do not
expose port 5000 to anything beyond a trusted network.

---

## 2. The 7″ touchscreen kiosk

For the generic 1024×600 HDMI capacitive panel (USB touch).

### Wiring

The panel has three ports. Which one powers it matters.

```
        7" 1024x600 panel                      Raspberry Pi
   +--------------------------+
   |  HDMI  ------------------+------------>  HDMI0  (micro-HDMI on Pi 4/5;
   |                          |              the port nearest the USB-C
   |                          |              power jack = HDMI-A-1)
   |                          |
   |  TOUCH ------------------+------------>  any USB-A port  (HID data)
   |                          |
   |  POWER <-----------------+---- its own 5V supply, NOT the Pi
   +--------------------------+
                                             Pi <--- its own official PSU
```

- **HDMI** must go to **HDMI0** on a Pi 4/5 — the port closest to the USB-C
  power jack. That is the connector the kernel calls `HDMI-A-1`, which is what
  the `video=` line below targets.
- **TOUCH** is a USB HID connection; no driver is needed.
- **POWER** gets its own supply. These panels will usually light up from the
  TOUCH port alone, which is the tempting and wrong option: the panel then
  draws ~0.5-1 A through the Pi's 5 V rail. Keep the two independent.

If the panel has the built-in USB hub variant it also exposes USB-A sockets,
useful for a keyboard during setup — but they draw from the panel's supply,
another reason to give it a real one.

Connect everything before powering the Pi.

### Display

Touch is a USB HID device and needs no driver. Video usually does need one
line, because these panels often report bad or missing EDID and the Pi then
picks 1080p and shows nothing. Append to the single line in
`/boot/firmware/cmdline.txt`:

```
video=HDMI-A-1:1024x600M@60D
```

`HDMI-A-1` is HDMI0 on a Pi 4/5; `D` forces digital output. Reboot, then
confirm with `kmsprint` or `wlr-randr`.

The widely-copied `hdmi_cvt` / `hdmi_group` / `hdmi_mode` lines in `config.txt`
are **firmware-KMS** options. Current Pi OS uses full KMS (`vc4-kms-v3d`) and
ignores them — which is why adding them appears to do nothing.

### Verifying

Check the two halves separately, so a fault points at one of them:

```bash
# Display: should list HDMI-A-1 at 1024x600
wlr-randr                  # or: kmsprint | grep -A2 HDMI

# Touch: should show a device with Touchscreen capability
libinput list-devices | grep -iB2 -A6 touch

# Live touch events -- tap the screen and watch coordinates
sudo libinput debug-events
```

A black screen is almost always the EDID/mode problem above, so check
`cmdline.txt` first. A working display with touches landing in the wrong place
is the rotation case below, not a driver fault.

If the panel is mounted portrait, `wlr-randr --output HDMI-A-1 --transform 90`.
Under Wayland the touch input follows the output transform automatically; this
was the miserable part under X11 and is now free.

### Browser

```bash
sudo apt install -y chromium-browser
mkdir -p ~/.config/autostart
sed "s|/home/kdcberry/LabManagement|$HOME/LabManagement|" \
    ~/LabManagement/deploy/kiosk/labmanager-kiosk.desktop \
    > ~/.config/autostart/labmanager-kiosk.desktop
```

Try it by hand before trusting autostart:

```bash
bash ~/LabManagement/deploy/kiosk/start-kiosk.sh
```

`start-kiosk.sh` waits for `/api/health` before launching (so a slow boot does
not land on an error page), suppresses screen blanking under both Wayland and
X11, and clears Chromium's "didn't shut down correctly" bar — which otherwise
makes the kiosk look broken after every power cut.

### Power

Give the panel its own supply. Sharing the Pi's is the single most common cause
of "random display failures" and, on this hardware specifically, of the
undervoltage chain described above.

---

## Known gaps

- **No authentication.** Anyone who can reach the port has full write access.
  Fine behind Tailscale or a trusted LAN; not fine on a shared network.
- **The UI is not yet touch-sized.** At 1024×600 the current pages are cramped —
  about ten rows of usable height. A purpose-built kiosk view for the −80
  (rack grid → box stack → contents, three taps, no keyboard) is the next piece
  of work. Until then the kiosk is usable but not pleasant.
- **One writer at a time.** SQLite with a handful of lab users is fine, but
  there is no attribution: nothing records who changed what.
