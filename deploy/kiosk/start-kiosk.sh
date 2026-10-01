#!/usr/bin/env bash
#
# Launch Chromium full-screen against the local server, for the 7" panel.
#
# Autostarted via deploy/kiosk/labmanager-kiosk.desktop. Run it by hand first
# to check it behaves:  bash deploy/kiosk/start-kiosk.sh

set -uo pipefail

URL="${KIOSK_URL:-http://localhost:5000/}"
PROFILE="${KIOSK_PROFILE:-$HOME/.config/labmanager-kiosk}"

# Wait for the service rather than racing it at boot.
for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 "${URL%/}/api/health" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Stop the screen blanking. Which tool applies depends on the session:
# Pi OS Trixie defaults to Wayland/labwc, where xset does not exist.
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    # wlopm ships with Pi OS's labwc session; harmless if absent.
    command -v wlopm >/dev/null && wlopm --on '*' 2>/dev/null || true
    # Also disable the compositor's own idle timeout if swayidle is running.
    pkill -x swayidle 2>/dev/null || true
else
    command -v xset >/dev/null && { xset s off; xset -dpms; xset s noblank; } || true
fi

# Chromium on Pi OS is `chromium-browser` on older images, `chromium` on newer.
BROWSER=$(command -v chromium-browser || command -v chromium) || {
    echo "No chromium found. sudo apt install -y chromium-browser" >&2
    exit 1
}

# A stale "Chromium didn't shut down correctly" bar makes the kiosk look broken
# after a power cut, so clear the exit flags before each launch.
PREFS="$PROFILE/Default/Preferences"
if [[ -f "$PREFS" ]]; then
    sed -i 's/"exit_type":"[^"]*"/"exit_type":"Normal"/; s/"exited_cleanly":false/"exited_cleanly":true/' \
        "$PREFS" 2>/dev/null || true
fi

exec "$BROWSER" \
    --kiosk \
    --app="$URL" \
    --user-data-dir="$PROFILE" \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --no-first-run \
    --check-for-update-interval=31536000 \
    --overscroll-history-navigation=0 \
    --disable-pinch \
    --password-store=basic
