#!/usr/bin/env bash
# Push code from laptop to Lightsail and (re)start the backend.
#
# rsyncs the source tree (minus build/data junk), then SSHes in and runs
# the idempotent setup script. First run does apt install + Caddy + venv;
# subsequent runs are mostly a `pip install -e` + `systemctl restart`.
#
# Usage:
#   echo 'LIGHTSAIL_HOST=tennismob-prod' > .deploy.env  # one-time
#   scripts/deploy.sh                                    # every deploy
#
# .env on the box is preserved across deploys (it's in the rsync exclude list).
# The local SQLite DB is also excluded — use scripts/seed-db.sh for that.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.deploy.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.deploy.env"
    set +a
fi

: "${LIGHTSAIL_HOST:?Set LIGHTSAIL_HOST (e.g. 'tennismob-prod') in env or .deploy.env}"
REMOTE_DIR=${REMOTE_DIR:-/opt/tennismob}

# ---- Sync ------------------------------------------------------------------

# Make sure the destination exists, then rsync over SSH with the *remote*
# rsync running as root (`--rsync-path='sudo rsync'`). Lightsail's ubuntu
# user has passwordless sudo, so this works out of the box. Running rsync
# as root means it can write into directories already chowned to tennismob
# from a previous setup pass, and we don't have to do an ownership
# ping-pong on every deploy. setup.sh re-chowns to tennismob at the end.
echo "==> Preparing remote dir on $LIGHTSAIL_HOST"
ssh "$LIGHTSAIL_HOST" "sudo mkdir -p $REMOTE_DIR"

echo "==> Syncing source"
rsync -az --delete \
    --rsync-path='sudo rsync' \
    --exclude='.git/' \
    --exclude='node_modules/' \
    --exclude='.next/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.egg-info/' \
    --exclude='data/' \
    --exclude='.env' \
    --exclude='.deploy.env' \
    --exclude='.claude/' \
    --exclude='.expo/' \
    --exclude='.DS_Store' \
    --exclude='*.log' \
    "$REPO_ROOT/" "$LIGHTSAIL_HOST:$REMOTE_DIR/"

# ---- Setup / restart -------------------------------------------------------

echo "==> Running setup on box"
ssh "$LIGHTSAIL_HOST" "sudo bash $REMOTE_DIR/backend/deploy/setup.sh"

# ---- Health check ----------------------------------------------------------

# Skip the health check on first run — the user still needs to fill in .env
# and the API_TENNIS_KEY before the service can start. The setup script
# prints clear next-steps when that's the case and exits 0.
# .env is 0600 tennismob:tennismob so we sudo-grep to avoid a noisy
# "Permission denied" from the ubuntu shell.
if ssh "$LIGHTSAIL_HOST" 'sudo test -f /opt/tennismob/backend/.env && sudo grep -q "^API_TENNIS_KEY=." /opt/tennismob/backend/.env' 2>/dev/null; then
    echo "==> Health check"
    sleep 2
    if curl -fsS --max-time 10 https://api.mob.tennis/health >/dev/null 2>&1; then
        echo "    api.mob.tennis is up"
    elif ssh "$LIGHTSAIL_HOST" "curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null"; then
        echo "    Backend is up locally on the box, but https://api.mob.tennis isn't reachable yet."
        echo "    Likely DNS still propagating, or 80/443 not open in Lightsail firewall."
    else
        echo "    Health check failed — inspect: ssh $LIGHTSAIL_HOST 'journalctl -u tennismob -n 80'" >&2
        exit 1
    fi
fi
