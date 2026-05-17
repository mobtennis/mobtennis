#!/usr/bin/env bash
# Upload the local SQLite database to Lightsail.
#
# Use this to seed the production box with your dev DB on first deploy, or
# to restore from a known-good local copy. Stops the backend during the
# swap so SQLite isn't mid-write when we replace the file.
#
# Usage:
#   LIGHTSAIL_HOST=ubuntu@1.2.3.4 scripts/seed-db.sh
#   # Or with .deploy.env (same as scripts/deploy.sh)
#   scripts/seed-db.sh
#
# Defaults to data/tennismob.db; override with LOCAL_DB=...

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.deploy.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.deploy.env"
    set +a
fi

: "${LIGHTSAIL_HOST:?Set LIGHTSAIL_HOST (e.g. 'ubuntu@1.2.3.4')}"

LOCAL_DB=${LOCAL_DB:-"$REPO_ROOT/data/tennismob.db"}
REMOTE_PATH=${REMOTE_PATH:-/opt/tennismob/data/tennismob.db}

if [ ! -f "$LOCAL_DB" ]; then
    echo "Local DB not found: $LOCAL_DB" >&2
    exit 1
fi

# Final confirmation — this overwrites production data.
SIZE=$(du -h "$LOCAL_DB" | cut -f1)
echo "About to upload $LOCAL_DB ($SIZE) to $LIGHTSAIL_HOST:$REMOTE_PATH"
echo "Backend will be stopped during the swap and the existing remote DB will be backed up first."
read -r -p "Continue? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 1
fi

# Upload to /tmp first so we can do an atomic install once the backend is stopped.
echo "==> Uploading"
scp "$LOCAL_DB" "$LIGHTSAIL_HOST:/tmp/tennismob.seed.db"

# Stop, back up the existing DB (if any), atomically replace, restart.
echo "==> Swapping on remote"
ssh "$LIGHTSAIL_HOST" bash -s <<'REMOTE'
set -euo pipefail
sudo systemctl stop tennismob

if [ -f /opt/tennismob/data/tennismob.db ]; then
    STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    sudo cp /opt/tennismob/data/tennismob.db "/opt/tennismob/data/tennismob.db.bak.$STAMP"
    echo "    backed up previous db to tennismob.db.bak.$STAMP"
fi

sudo install -o tennismob -g tennismob -m 644 /tmp/tennismob.seed.db /opt/tennismob/data/tennismob.db
# Drop the WAL/SHM if they exist — they'd be stale relative to the new main file.
sudo rm -f /opt/tennismob/data/tennismob.db-wal /opt/tennismob/data/tennismob.db-shm
sudo rm -f /tmp/tennismob.seed.db

sudo systemctl start tennismob
REMOTE

# Smoke-check the API
echo "==> Health check"
sleep 2
if curl -fsS --max-time 10 https://api.mob.tennis/health >/dev/null; then
    echo "    api.mob.tennis is up"
else
    echo "    Health check failed — inspect: ssh $LIGHTSAIL_HOST 'journalctl -u tennismob -n 80'" >&2
    exit 1
fi
