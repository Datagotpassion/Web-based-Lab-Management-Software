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
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / 'lab_management.db'

PI_HOST = os.environ.get('LABPI_HOST', '10.81.83.241')
PI_USER = os.environ.get('LABPI_USER', 'kdcberry')
SSH_KEY = os.environ.get('LABPI_KEY', str(Path.home() / '.ssh' / 'id_ed25519_labpi'))
REMOTE_DIR = os.environ.get('LABPI_DIR', '/home/kdcberry/LabManagement')
REMOTE_DB = f'{REMOTE_DIR}/lab_management.db'

SSH_BASE = ['-i', SSH_KEY, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=accept-new']


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ssh(command, timeout=60):
    return run(['ssh', *SSH_BASE, f'{PI_USER}@{PI_HOST}', command], timeout=timeout)


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

        if remote_hash is None:
            # Unreachable is normal: the Pi may be off, or this machine may be
            # on a different network. Not an error worth alarming about.
            say(f'{PI_HOST} unreachable; nothing sent.')
            return 0

        if args.status:
            print(f'  PC  : {local_hash[:16]}')
            print(f'  Pi  : {remote_hash[:16]}')
            print('  in sync' if local_hash == remote_hash else '  OUT OF SYNC')
            return 0

        if local_hash == remote_hash and not args.force:
            say('Already in sync; nothing sent.')
            return 0

        # Land it beside the target first, then rename: mv within a filesystem
        # is atomic, so a reader never observes a partial file.
        staged = f'{REMOTE_DB}.incoming'
        cp = run(['scp', *SSH_BASE, str(local_snap),
                  f'{PI_USER}@{PI_HOST}:{staged}'], timeout=120)
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

        say(f'Synced {local_snap.stat().st_size:,} bytes to {PI_HOST} '
            f'({local_hash[:16]})')
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
