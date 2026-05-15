#!/usr/bin/env bash
# Installs the Job Application Agent scraper on a Debian-family VM.
# Two-phase install:
#   Phase 1 (first run): create user, generate SSH key, print public key, exit.
#     You add the key to GitHub repo → Settings → Deploy keys (read-only).
#   Phase 2 (re-run): clone the repo via SSH, install Python deps, set up systemd.
# Idempotent — safe to re-run for updates.

set -euo pipefail

REPO_URL="${REPO_URL:-git@github.com:JustinoChan/Job-Application-Agent.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/job-application-agent}"
SERVICE_USER="${SERVICE_USER:-scraper}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Re-running with sudo..." >&2
    exec sudo -E "$0" "$@"
fi

echo ">>> Installing system packages"
apt-get update -qq
apt-get install -y --no-install-recommends git openssh-client python3 python3-venv python3-pip ca-certificates

echo ">>> Creating service user $SERVICE_USER"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
fi

KEY_PATH="/home/$SERVICE_USER/.ssh/id_ed25519"

if [ ! -f "$KEY_PATH" ]; then
    echo ">>> Generating SSH key for $SERVICE_USER (one-time)"
    sudo -u "$SERVICE_USER" mkdir -p "/home/$SERVICE_USER/.ssh"
    sudo -u "$SERVICE_USER" chmod 700 "/home/$SERVICE_USER/.ssh"
    sudo -u "$SERVICE_USER" ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "scraper@$(hostname)"
    sudo -u "$SERVICE_USER" bash -c "ssh-keyscan -t ed25519 github.com >> /home/$SERVICE_USER/.ssh/known_hosts 2>/dev/null"
    echo ""
    echo "==============================================================================="
    echo "  Add this public key to GitHub:"
    echo "    Repo → Settings → Deploy keys → Add deploy key"
    echo "    Title: gcp-scraper-vm"
    echo "    Allow write access: NO"
    echo "==============================================================================="
    cat "$KEY_PATH.pub"
    echo "==============================================================================="
    echo ""
    echo "After adding the deploy key on GitHub, re-run this script:"
    echo "  sudo bash $0"
    exit 0
fi

echo ">>> Verifying SSH access to GitHub"
# ssh -T git@github.com always exits 1 (no shell access). Capture output instead
# of relying on the exit code, so `set -o pipefail` doesn't false-fail this check.
SSH_PROBE_OUTPUT=$(sudo -u "$SERVICE_USER" ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 || true)
if ! echo "$SSH_PROBE_OUTPUT" | grep -q "successfully authenticated"; then
    echo "ERROR: SSH key not yet accepted by GitHub." >&2
    echo "ssh probe output was:" >&2
    echo "$SSH_PROBE_OUTPUT" >&2
    echo "Add /home/$SERVICE_USER/.ssh/id_ed25519.pub as a Deploy key on the repo first." >&2
    exit 1
fi

echo ">>> Cloning / updating repo at $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
if [ ! -d "$INSTALL_DIR/.git" ]; then
    sudo -u "$SERVICE_USER" git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
else
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" pull --ff-only
fi
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo ">>> Creating Python venv and installing deps"
sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/scraper/.venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/scraper/.venv/bin/pip" install --upgrade pip --quiet
sudo -u "$SERVICE_USER" "$INSTALL_DIR/scraper/.venv/bin/pip" install -r "$INSTALL_DIR/scraper/requirements.txt" --quiet

echo ">>> Setting up .env"
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
echo "  1. Edit $INSTALL_DIR/scraper/.env and set API_TOKEN"
echo "       sudo nano $INSTALL_DIR/scraper/.env"
echo "  2. Self-test against your tunnel:"
echo "       sudo -u $SERVICE_USER $INSTALL_DIR/scraper/.venv/bin/python -m scraper.main --self-test"
echo "  3. Enable the timer:"
echo "       sudo systemctl enable --now scraper.timer"
echo "       systemctl list-timers scraper.timer"
echo "       journalctl -u scraper.service --since today"
