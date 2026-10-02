"""Open the Lab Management System as an app window.

Double-clicked from a shortcut. Starts the server if it is not already up,
waits for it to answer, then opens a browser in app mode -- no address bar, no
tabs, its own taskbar button. Closing the window leaves the server running, so
reopening is instant and the display keeps syncing.

.pyw rather than .py so Windows uses pythonw and no console window appears.
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent

# Where the running window's process id is remembered between launches.
STATE_DIR = Path(os.environ.get('LOCALAPPDATA', HERE)) / 'LabManagement'
STATE_FILE = STATE_DIR / 'window.json'
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


# ----------------------------------------------------------- single instance
#
# Opening the app twice gives two windows onto the same database, which is
# both confusing and a way to save over your own edits. A second launch should
# simply bring the existing window forward.

def _process_alive(pid):
    PROCESS_QUERY_LIMITED = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not handle:
        return False
    exit_code = wintypes.DWORD()
    ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(handle)
    STILL_ACTIVE = 259
    return bool(ok) and exit_code.value == STILL_ACTIVE


def _focus_window_of(pid):
    """Bring that process's first visible top-level window to the front."""
    user32 = ctypes.windll.user32
    found = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            if user32.GetWindowTextLengthW(hwnd) > 0:   # skip hidden helpers
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(WNDENUMPROC(visit), 0)
    if not found:
        return False

    hwnd = found[0]
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    # SetForegroundWindow is refused unless the calling thread is allowed to
    # steal focus, so attach to the window's input queue first.
    kernel32 = ctypes.windll.kernel32
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    our_thread = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(our_thread, target_thread, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(our_thread, target_thread, False)
    return True


def focus_existing():
    """True if an app window was already open and has been brought forward."""
    try:
        pid = json.loads(STATE_FILE.read_text()).get('browser_pid')
    except (OSError, ValueError, AttributeError):
        return False
    if not pid or not _process_alive(pid):
        return False
    return _focus_window_of(pid)


def remember(pid):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({'browser_pid': pid}))
    except OSError:
        pass


def main():
    # Already open? Bring it forward and leave, rather than opening a second
    # window onto the same database.
    if focus_existing():
        return

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

    proc = subprocess.Popen([
        str(browser),
        f'--app={URL}',
        f'--user-data-dir={profile}',
        '--window-size=1500,950',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=TranslateUI',
    ], creationflags=DETACHED_PROCESS, close_fds=True)

    # Remember which process owns the window, so a later launch can focus it.
    # The window takes a moment to appear; recording the pid immediately is
    # enough, since focus_existing only looks for windows once asked.
    remember(proc.pid)


if __name__ == '__main__':
    main()
