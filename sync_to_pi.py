"""Push the authoritative database from this PC to the freezer display.

The lab PC holds the real database; the Pi by the -80 runs a read-only replica
so people can look things up without walking back here. This copies the PC's
database over, one way, never the reverse.

One-way replication on purpose: the Pi never writes, so there is nothing to
merge and no conflicts to resolve. The Pi enforces that itself via
LABMANAGER_READONLY, since a write accepted there would be silently destroyed
by the next run of this script.

Safe to run on a timer. Three details that matter:

  * the snapshot is taken with sqlite's backup API, not a file copy, so a sync
    landing mid-write cannot produce a torn database;
  * nothing is sent when the content has not changed, so a minute-by-minute
    timer costs nothing;
  * the file is moved into place on the Pi with mv, which is atomic within a
    filesystem, so a reader never sees a half-written database.

Usage:
    python sync_to_pi.py            # sync if changed
    python sync_to_pi.py --force    # sync regardless
    python sync_to_pi.py --status   # report both sides, change nothing
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / 'lab_management.db'

# Reach the display by name, not address. Moving it to another socket gets it
# a new DHCP lease, and a hardcoded address would then point at nothing -- so
# mDNS does the lookup and the last address that worked is kept as a fallback
# for when mDNS is slow or blocked.
PI_HOST = os.environ.get('LABPI_HOST', 'labfridge.local')
PI_USER = os.environ.get('LABPI_USER', 'kdcberry')
SSH_KEY = os.environ.get('LABPI_KEY', str(Path.home() / '.ssh' / 'id_ed25519_labpi'))
REMOTE_DIR = os.environ.get('LABPI_DIR', '/home/kdcberry/LabManagement')
REMOTE_DB = f'{REMOTE_DIR}/lab_management.db'

# Last working address and last successful sync, so a quietly broken sync can
# be noticed rather than just going stale.
STATE = Path(__file__).parent / '.sync_state.json'

SSH_BASE = ['-i', SSH_KEY, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=accept-new']


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(**fields):
    state = load_state()
    state.update(fields)
    try:
        STATE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# Resolved once per run: the name if it answers, else whatever address worked
# last time.
_HOST = None


def host():
    global _HOST
    if _HOST:
        return _HOST
    candidates = [PI_HOST]
    last = load_state().get('address')
    if last and last != PI_HOST:
        candidates.append(last)
    for cand in candidates:
        probe = run(['ssh', *SSH_BASE, f'{PI_USER}@{cand}', 'true'], timeout=20)
        if probe.returncode == 0:
            _HOST = cand
            return cand
    _HOST = PI_HOST          # unreachable; report against the canonical name
    return _HOST


def ssh(command, timeout=60):
    return run(['ssh', *SSH_BASE, f'{PI_USER}@{host()}', command], timeout=timeout)


def snapshot(dest):
    """Consistent copy of the live database, safe to take while it is in use."""
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dst = sqlite3.connect(dest)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def remote_sha():
    r = ssh(f'sha256sum {REMOTE_DB} 2>/dev/null | cut -d" " -f1')
    return r.stdout.strip() if r.returncode == 0 else None


def _resolved_address():
    """The display's current numeric address, cached as a fallback for when
    mDNS stops answering."""
    r = ssh("hostname -I | awk '{print $1}'", timeout=20)
    addr = r.stdout.strip() if r.returncode == 0 else ''
    return addr or load_state().get('address')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--force', action='store_true',
                    help='send even if the content is unchanged')
    ap.add_argument('--status', action='store_true',
                    help='report both sides without changing anything')
    ap.add_argument('--quiet', action='store_true',
                    help='only report problems (for scheduled runs)')
    args = ap.parse_args()

    def say(msg):
        if not args.quiet:
            print(msg)

    if not DB.exists():
        print(f'No database at {DB}', file=sys.stderr)
        return 1

    tmp_dir = tempfile.mkdtemp(prefix='labsync_')
    local_snap = Path(tmp_dir) / 'lab_management.db'
    try:
        snapshot(local_snap)
        local_hash = sha256(local_snap)
        remote_hash = remote_sha()

        if args.status:
            state = load_state()
            print(f'  target     : {host()}')
            print(f'  last synced: {state.get("last_sync", "never")}')
            print(f'  PC         : {local_hash[:16]}')
            if remote_hash is None:
                print('  Pi         : unreachable')
            else:
                print(f'  Pi         : {remote_hash[:16]}')
                print('  in sync' if local_hash == remote_hash else '  OUT OF SYNC')
            return 0

        if remote_hash is None:
            # Unreachable is routine -- the Pi may be off, or this machine on a
            # different network -- so this is not an error. The display shows
            # how old its own copy is, which is where staleness becomes visible.
            say(f'{host()} unreachable; nothing sent.')
            save_state(last_failure=datetime.now().isoformat(timespec='seconds'))
            return 0

        if local_hash == remote_hash and not args.force:
            say('Already in sync; nothing sent.')
            save_state(last_sync=datetime.now().isoformat(timespec='seconds'),
                       address=_resolved_address())
            return 0

        # Land it beside the target first, then rename: mv within a filesystem
        # is atomic, so a reader never observes a partial file.
        staged = f'{REMOTE_DB}.incoming'
        cp = run(['scp', *SSH_BASE, str(local_snap),
                  f'{PI_USER}@{host()}:{staged}'], timeout=120)
        if cp.returncode != 0:
            print(f'Copy failed: {cp.stderr.strip()}', file=sys.stderr)
            return 1

        mv = ssh(f'mv -f {staged} {REMOTE_DB}')
        if mv.returncode != 0:
            print(f'Install failed: {mv.stderr.strip()}', file=sys.stderr)
            ssh(f'rm -f {staged}')
            return 1

        confirmed = remote_sha()
        if confirmed != local_hash:
            print('Verification failed: hashes differ after copy',
                  file=sys.stderr)
            return 1

        say(f'Synced {local_snap.stat().st_size:,} bytes to {host()} '
            f'({local_hash[:16]})')
        save_state(last_sync=datetime.now().isoformat(timespec='seconds'),
                   address=_resolved_address())
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
