#!/usr/bin/env bash
# Idempotent setup + restart on the Lightsail box. Invoked by the laptop's
# scripts/deploy.sh after rsync. Safe to re-run any time.
#
# First invocation on a fresh box: installs system packages, Caddy, the
# tennismob system user, the venv, and bails after dropping a .env template
# so the operator can fill in secrets. Re-run starts services.
#
# Subsequent invocations: refresh deps, re-install configs (cheap if
# unchanged), restart the backend, reload Caddy.

set -euo pipefail

APP_DIR=/opt/tennismob

if [ "$EUID" -ne 0 ]; then
    echo "Run as root (the laptop's scripts/deploy.sh handles this for you)." >&2
    exit 1
fi

# 1. Service user
if ! id tennismob >/dev/null 2>&1; then
    useradd --system --create-home --shell /bin/bash tennismob
fi

# 2. System packages. Ubuntu 24.04 ships python3.12 preinstalled but *not*
# python3.12-venv (no `ensurepip`). Listing both unconditionally — apt-get
# install is a no-op for packages already at the latest version, so this
# stays cheap on subsequent runs.
apt-get update -qq
apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    rsync curl ca-certificates

# 2b. Disable Ubuntu's auto-update timers. For a single-purpose VM we
# manage updates manually via this script — the default daily apt-daily
# / apt-daily-upgrade / unattended-upgrades units download packages and
# briefly pin CPU + I/O, which has correlated with the box going
# unreachable on long uptimes. Idempotent (`|| true` in case the unit
# isn't installed). Re-enable later with `systemctl enable --now <unit>`.
for unit in unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer; do
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
done

# 3. Caddy from the official repo. Caddy's published instructions add
# debian-keyring + debian-archive-keyring, but those are Debian-only and
# don't exist in Ubuntu's repos — and they aren't actually needed for the
# Cloudsmith-hosted GPG key, so we skip them.
if ! command -v caddy >/dev/null 2>&1; then
    apt-get install -y apt-transport-https gnupg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
        gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
        tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
fi

# 4. Take ownership of the synced source — rsync ran as the SSH user.
chown -R tennismob:tennismob "$APP_DIR"

# 5. venv + deps (FastAPI, SQLModel, etc.)
# A half-failed previous run can leave a venv with python but no pip
# (e.g. when python3.12-venv was missing). We probe both: python must
# import the stdlib, and `python -m pip` must work.
VENV="$APP_DIR/backend/.venv"
venv_ok() {
    [ -x "$VENV/bin/python" ] \
        && "$VENV/bin/python" -c 'import sys' >/dev/null 2>&1 \
        && "$VENV/bin/python" -m pip --version >/dev/null 2>&1
}
if ! venv_ok; then
    rm -rf "$VENV"
    sudo -u tennismob python3.12 -m venv "$VENV"
    sudo -u tennismob "$VENV/bin/python" -m pip install --upgrade pip --quiet
fi
sudo -u tennismob "$VENV/bin/python" -m pip install -e "$APP_DIR/backend" --quiet

# 6. Data dir (SQLite + any cached files)
mkdir -p "$APP_DIR/data"
chown -R tennismob:tennismob "$APP_DIR/data"

# 7. .env — bail on first run so the operator can fill in secrets
if [ ! -f "$APP_DIR/backend/.env" ]; then
    cp "$APP_DIR/backend/deploy/.env.example" "$APP_DIR/backend/.env"
    chown tennismob:tennismob "$APP_DIR/backend/.env"
    chmod 600 "$APP_DIR/backend/.env"
    echo
    echo "==> Created $APP_DIR/backend/.env from template."
    echo "    Edit it on the box:"
    echo "      ssh <host>"
    echo "      sudo -u tennismob nano /opt/tennismob/backend/.env"
    echo "    Set API_TENNIS_KEY (and CORS_ORIGINS if needed), then re-run scripts/deploy.sh."
    exit 0
fi

# 8. systemd unit
install -m 644 "$APP_DIR/backend/deploy/tennismob.service" /etc/systemd/system/tennismob.service
systemctl daemon-reload
systemctl enable tennismob.service >/dev/null 2>&1 || true
systemctl restart tennismob.service

# 9. Caddy
install -m 644 "$APP_DIR/backend/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl reload caddy

echo
echo "==> Setup complete."
echo "    Backend: systemctl status tennismob"
echo "    Caddy:   systemctl status caddy"
echo "    Logs:    journalctl -u tennismob -f"
