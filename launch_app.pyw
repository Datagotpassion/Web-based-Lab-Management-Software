"""Open the Lab Management System as an app window.

Double-clicked from a shortcut. Starts the server if it is not already up,
waits for it to answer, then opens a browser in app mode -- no address bar, no
tabs, its own taskbar button. Closing the window leaves the server running, so
reopening is instant and the display keeps syncing.

.pyw rather than .py so Windows uses pythonw and no console window appears.
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
PORT = int(os.environ.get('LABMANAGER_PORT', '5000'))
URL = f'http://localhost:{PORT}/'
HEALTH = f'{URL}api/health'

# Chromium-based browsers only: --app is what removes the browser furniture.
BROWSERS = [
    Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
        / 'Microsoft/Edge/Application/msedge.exe',
    Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
        / 'Microsoft/Edge/Application/msedge.exe',
    Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
        / 'Google/Chrome/Application/chrome.exe',
    Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
        / 'Google/Chrome/Application/chrome.exe',
    Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe',
]

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def server_up(timeout=1.5):
    try:
        with urllib.request.urlopen(HEALTH, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def start_server():
    """Launch waitress detached, so closing this launcher leaves it running."""
    pythonw = HERE / 'venv' / 'Scripts' / 'pythonw.exe'
    if not pythonw.exists():
        pythonw = Path(sys.executable).with_name('pythonw.exe')
    subprocess.Popen(
        [str(pythonw), str(HERE / 'serve.py'), '--port', str(PORT)],
        cwd=str(HERE),
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        close_fds=True,
    )


def find_browser():
    for path in BROWSERS:
        if path.exists():
            return path
    return None


def main():
    if not server_up():
        start_server()
        # Waitress starts in well under a second; allow generously for a cold
        # disk without making a healthy start feel slow.
        for _ in range(40):
            if server_up(timeout=1):
                break
            time.sleep(0.25)
        else:
            # Fall through and open anyway: a visible error page beats a
            # launcher that silently does nothing.
            pass

    browser = find_browser()
    if browser is None:
        # No Chromium browser: the default handler at least opens the app.
        os.startfile(URL)
        return

    # A dedicated profile keeps the window's size, zoom and position separate
    # from normal browsing, so it behaves like its own application.
    profile = Path(os.environ['LOCALAPPDATA']) / 'LabManagement' / 'browser'
    profile.mkdir(parents=True, exist_ok=True)

    subprocess.Popen([
        str(browser),
        f'--app={URL}',
        f'--user-data-dir={profile}',
        '--window-size=1500,950',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=TranslateUI',
    ], creationflags=DETACHED_PROCESS, close_fds=True)


if __name__ == '__main__':
    main()
