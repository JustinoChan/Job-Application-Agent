#!/usr/bin/env bash
# Installs the Job Application Agent scraper on a Debian-family VM.
# Run as a user with sudo. Idempotent — safe to re-run.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/JustinoChan/Job-Application-Agent.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/job-application-agent}"
SERVICE_USER="${SERVICE_USER:-scraper}"

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Re-running with sudo..." >&2
        exec sudo -E "$0" "$@"
    fi
}

require_root "$@"

echo ">>> Installing system packages"
apt-get update -qq
apt-get install -y --no-install-recommends git python3 python3-venv python3-pip ca-certificates

echo ">>> Creating service user $SERVICE_USER"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

echo ">>> Cloning / updating repo at $INSTALL_DIR"
if [ ! -d "$INSTALL_DIR/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
    git -C "$INSTALL_DIR" pull --ff-only
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo ">>> Creating Python venv and installing deps"
sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/scraper/.venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/scraper/.venv/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$INSTALL_DIR/scraper/.venv/bin/pip" install -r "$INSTALL_DIR/scraper/requirements.txt"

echo ">>> Setting up .env (you'll need to edit this)"
if [ ! -f "$INSTALL_DIR/scraper/.env" ]; then
    cp "$INSTALL_DIR/scraper/.env.example" "$INSTALL_DIR/scraper/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/scraper/.env"
    chmod 600 "$INSTALL_DIR/scraper/.env"
    echo "   created $INSTALL_DIR/scraper/.env — edit it and set API_TOKEN before enabling the timer"
else
    echo "   .env already exists, leaving as-is"
fi

echo ">>> Installing systemd unit + timer"
install -m 644 "$INSTALL_DIR/scraper/deploy/scraper.service" /etc/systemd/system/scraper.service
install -m 644 "$INSTALL_DIR/scraper/deploy/scraper.timer"   /etc/systemd/system/scraper.timer
systemctl daemon-reload

echo ""
echo "Install complete."
echo ""
echo "Next steps:"
echo "  1. Edit /opt/job-application-agent/scraper/.env and set API_TOKEN"
echo "  2. Run a self-test:"
echo "       sudo -u $SERVICE_USER $INSTALL_DIR/scraper/.venv/bin/python -m scraper.main --self-test"
echo "  3. Enable the timer:"
echo "       sudo systemctl enable --now scraper.timer"
echo "  4. Check status:"
echo "       systemctl list-timers scraper.timer"
echo "       journalctl -u scraper.service --since today"
