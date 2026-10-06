#!/usr/bin/env bash
#
# Set up (or re-run safely on) a Raspberry Pi to serve the Lab Management
# System as a systemd service. Idempotent: running it again just updates.
#
#   curl -fsSL <raw url>/deploy/setup-pi.sh | bash     # or, having cloned:
#   cd ~/LabManagement && bash deploy/setup-pi.sh
#
# Deliberately does NOT install or configure the touchscreen kiosk -- get the
# service working and reachable first. See deploy/README.md for the kiosk.

set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/LabManagement}"
SERVICE_NAME="labmanager"
PORT="${LABMANAGER_PORT:-5000}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m !  %s\033[0m\n' "$1"; }

if [[ ! -d "$REPO_DIR" ]]; then
    echo "No checkout at $REPO_DIR." >&2
    echo "Clone it first, then re-run:" >&2
    echo "  git clone <repo url> $REPO_DIR" >&2
    exit 1
fi

cd "$REPO_DIR"

say "Python environment"
# All runtime deps are pure-Python (see requirements.txt), so a plain venv is
# fine and nothing needs to compile. If a compiled dep is ever added, recreate
# this with --system-site-packages and apt-install that dep.
if [[ ! -x venv/bin/python ]]; then
    python3 -m venv venv
    echo "created venv"
else
    echo "venv already present"
fi
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt
echo "dependencies installed:"
./venv/bin/pip list --format=freeze | grep -Ei 'flask|waitress|werkzeug' | sed 's/^/   /'

say "Database"
if [[ -f lab_management.db ]]; then
    echo "existing database kept ($(du -h lab_management.db | cut -f1))"
    ./venv/bin/python backup_db.py | tail -1
else
    warn "no lab_management.db here."
    warn "The app will create an empty one on first start. To bring your data"
    warn "across, copy it from the PC, e.g. from PowerShell:"
    warn "  scp 'D:\\Lab Management\\lab_management.db' ${USER}@$(hostname).local:$REPO_DIR/"
fi

say "systemd service"
# Rewrite the unit for whoever is actually running this, rather than assuming.
sed -e "s|/home/labuser/LabManagement|$REPO_DIR|g" \
    -e "s|^User=.*|User=$USER|" \
    -e "s|^Group=.*|Group=$(id -gn)|" \
    -e "s|^Environment=LABMANAGER_PORT=.*|Environment=LABMANAGER_PORT=$PORT|" \
    deploy/labmanager.service | sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME" >/dev/null
sudo systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "service active"
else
    warn "service did not come up. Recent log:"
    sudo journalctl -u "$SERVICE_NAME" -n 25 --no-pager
    exit 1
fi

say "Check"
if curl -fsS "http://localhost:${PORT}/api/health" >/tmp/lm_health.json 2>/dev/null; then
    cat /tmp/lm_health.json
    echo
else
    warn "health endpoint did not answer on port $PORT"
    exit 1
fi

cat <<EOF

$(hostname) is serving the Lab Management System.

  On the lab network:  http://$(hostname).local:${PORT}
  From the PC, check:  Invoke-RestMethod http://$(hostname).local:${PORT}/api/health

To update after pushing changes from the PC:
  cd $REPO_DIR && git pull && sudo systemctl restart ${SERVICE_NAME}

Logs:
  sudo journalctl -u ${SERVICE_NAME} -f

EOF
