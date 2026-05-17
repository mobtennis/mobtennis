# Deploying the backend to AWS Lightsail

Stack: Ubuntu 24.04 → systemd → uvicorn (single worker) ← Caddy (TLS) ←
internet. SQLite lives at `/opt/tennismob/data` and is backed up via
Lightsail's daily snapshots.

**The whole deploy story: `scripts/deploy.sh` from your laptop.** It rsyncs
the source to the box and runs an idempotent setup script there. No git
on the server, no PATs, no GitHub auth — only SSH.

## One-time setup

### 1. Provision in AWS Lightsail

1. **Create instance** — Lightsail → Create instance.
   - Region: closest to your traffic (e.g. `eu-west-1`).
   - Image: **Linux/Unix → OS Only → Ubuntu 24.04 LTS**.
   - Plan: **$5/mo** (1 GB RAM / 2 vCPU / 40 GB SSD).
   - Name: `tennismob-prod`.
2. **Attach a static IP** — Lightsail → Networking → Create static IP →
   attach to `tennismob-prod`. Free while attached.
3. **Open firewall ports** — instance → Networking → IPv4 firewall.
   Add `HTTP (80)` and `HTTPS (443)`. Leave `SSH (22)` as-is.

### 2. Set up your SSH alias on your laptop

Download the Lightsail default key from Account → SSH keys, save it as
`~/.ssh/lightsail-tennismob.pem`, `chmod 600`, then add to `~/.ssh/config`:

```
Host tennismob-prod
  HostName <static-ip>
  User ubuntu
  IdentityFile ~/.ssh/lightsail-tennismob.pem
  IdentitiesOnly yes
```

Test: `ssh tennismob-prod whoami` → should print `ubuntu`.

### 3. Point DNS at the box

In Route 53, on the `mob.tennis` zone:

| Record           | Type | Value                          |
|------------------|------|--------------------------------|
| `mob.tennis`     | A    | `76.76.21.21` (Vercel)         |
| `www.mob.tennis` | CNAME | `cname.vercel-dns.com`        |
| `api.mob.tennis` | A    | *Lightsail static IP*          |

Only `api.mob.tennis` matters for the backend; the other two are for the
Vercel-hosted web.

### 4. Deploy from your laptop

```bash
echo 'LIGHTSAIL_HOST=tennismob-prod' > .deploy.env  # one-time
scripts/deploy.sh
```

First run does:
1. Rsyncs your repo (excluding build artifacts, secrets, the local DB) to
   `/opt/tennismob/` on the box.
2. SSHes in and runs `backend/deploy/setup.sh` as root, which installs
   Python 3.12 + Caddy + the systemd unit, creates the `tennismob` system
   user, builds the venv, drops a `.env` template, and **exits** so you
   can fill in secrets.

Fill the secrets in:

```bash
ssh tennismob-prod
sudo -u tennismob nano /opt/tennismob/backend/.env
# Set API_TENNIS_KEY (and verify CORS_ORIGINS), save, exit.
exit
```

Re-run from your laptop — this time setup starts the services:

```bash
scripts/deploy.sh
```

Health check:

```bash
ssh tennismob-prod 'curl -s http://127.0.0.1:8000/health'    # local
curl -i https://api.mob.tennis/health                         # external (DNS + TLS)
```

The first external HTTPS request triggers Caddy to issue a Let's Encrypt
cert (~5–15 seconds added).

### 5. Seed the database

```bash
scripts/seed-db.sh
```

Stops the backend, scps your local SQLite up, swaps atomically, restarts.

## Subsequent deploys

Just:

```bash
scripts/deploy.sh
```

That's `rsync` + `pip install -e` + `systemctl restart` + Caddy reload + a
quick health check. ~30 seconds end to end.

## Backups

Lightsail → instance → Snapshots → enable **Automatic snapshots**. Keep
the last 7 days. SQLite + Caddy state are both on the local disk, so a
single snapshot covers everything we care about.

## Rollback

Revert locally and re-deploy:

```bash
git checkout <good-commit>
scripts/deploy.sh
```

To restore data, attach an older Lightsail snapshot as a new instance
and copy `data/tennismob.db` back via `scripts/seed-db.sh`.

## Common ops

| Task                          | Command                                          |
|-------------------------------|--------------------------------------------------|
| Tail backend logs             | `ssh tennismob-prod 'journalctl -u tennismob -f'`|
| Tail Caddy logs               | `ssh tennismob-prod 'journalctl -u caddy -f'`    |
| Restart backend (no rsync)    | `ssh tennismob-prod 'sudo systemctl restart tennismob'` |
| Open a Python shell on prod   | `ssh tennismob-prod 'sudo -u tennismob /opt/tennismob/backend/.venv/bin/python'` |
| Hand-edit DB                  | `ssh tennismob-prod 'sudo -u tennismob sqlite3 /opt/tennismob/data/tennismob.db'` |

## When to graduate

- **>1 vCPU sustained** for hours: bump to the $10 plan or move scheduler
  to a separate worker.
- **SQLite write contention**: migrate to RDS Postgres. Schemas already
  use SQLModel so the swap is config-only.
- **Push notification volume blows up**: move the Expo push call out of
  the live-poll path into a background queue (Redis + RQ or similar).
