#!/usr/bin/env bash
#
# Launch Chromium full-screen against the local server, for the 7" panel.
#
# Autostarted via deploy/kiosk/labmanager-kiosk.desktop. Run it by hand first
# to check it behaves:  bash deploy/kiosk/start-kiosk.sh

set -uo pipefail

URL="${KIOSK_URL:-http://localhost:5000/}"
PROFILE="${KIOSK_PROFILE:-$HOME/.config/labmanager-kiosk}"
LOG="${KIOSK_LOG:-$HOME/.local/state/labmanager-kiosk.log}"

# Keep our own log: launched from XDG autostart there is nowhere for stdout to
# go, so a failure leaves no trace at all.
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "=== kiosk start $(date -Is) ==="

# XDG autostart does not reliably export WAYLAND_DISPLAY, and without it the
# Wayland detection below fails, Chromium falls back to X11, and exits with
# "Missing X server". Find the compositor socket ourselves rather than trusting
# the inherited environment.
: "${XDG_RUNTIME_DIR:=/run/user/$(id -u)}"
export XDG_RUNTIME_DIR
if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
    for sock in "$XDG_RUNTIME_DIR"/wayland-[0-9]*; do
        if [[ -S "$sock" ]]; then
            export WAYLAND_DISPLAY="$(basename "$sock")"
            echo "detected compositor socket: $WAYLAND_DISPLAY"
            break
        fi
    done
fi

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

# Which browser to use.
#
#   KIOSK_BROWSER=chromium   full Chromium (default; needs a desktop session
#                            and comfortably more than 1 GB of RAM)
#   KIOSK_BROWSER=cog        WPE WebKit rendering straight to DRM/KMS -- no
#                            desktop, no X, no compositor. Far lighter, and
#                            the only realistic option on a Pi 2 / Zero.
#
# On a weak board, run Pi OS Lite and use cog: there is no desktop to load and
# nothing competing for the 1 GB.
KIOSK_BROWSER="${KIOSK_BROWSER:-chromium}"

if [[ "$KIOSK_BROWSER" == "cog" ]]; then
    COG=$(command -v cog) || {
        echo "cog not found. sudo apt install -y cog" >&2
        exit 1
    }
    # The DRM backend draws directly to the framebuffer and takes touch from
    # libinput, so this works on Pi OS Lite with no graphical session.
    export COG_PLATFORM_DRM_VIDEO_MODE="${COG_PLATFORM_DRM_VIDEO_MODE:-1024x600}"
    export WPE_DRM_LIBINPUT_SEAT="${WPE_DRM_LIBINPUT_SEAT:-seat0}"
    exec "$COG" --platform=drm "$URL"
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

# Chromium defaults to its X11 backend and dies with "Missing X server or
# $DISPLAY" on a Wayland-only session (Pi OS Trixie uses labwc), so the
# platform has to be named explicitly.
CHROME_FLAGS=()
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    CHROME_FLAGS+=(--ozone-platform=wayland)
fi

exec "$BROWSER" \
    "${CHROME_FLAGS[@]}" \
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
