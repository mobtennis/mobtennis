# Scheduled jobs on api.mob.tennis

There is **no OS-level crontab**. Every recurring task runs in-process via
**APScheduler** (`AsyncIOScheduler`), wired up in
[`backend/app/jobs/scheduler.py`](../app/jobs/scheduler.py) `start_scheduler()`,
started from the FastAPI lifespan in `app/main.py`.

Consequences of in-process scheduling:

- Jobs **only run while the `tennismob` systemd service is up**. A crash or
  redeploy pauses everything until boot; the boot one-shots (below) exist to
  reconcile state after downtime.
- The service runs **`--workers 1` on purpose** (see `deploy/tennismob.service`).
  APScheduler holds job state in-process; a second worker would duplicate every
  poll and blow the api-tennis quota. **Do not scale workers.**
- All cron times are **UTC**.

> **⚠️ Keep this file in sync.** If you add, remove, or re-time a job in
> `scheduler.py`, update the table here in the same change. An out-of-date list
> is worse than none. There's a pointer comment at the top of `start_scheduler()`
> to remind you.

## Recurring jobs

| Job ID | Trigger (UTC) | What it does |
|---|---|---|
| `poll_today` | every **1 h** | Refresh today's fixtures/schedule so the live cadence loop has fresh data. Real-time updates come from the WS loop (below); this is the REST backstop. |
| `sync_news` | every **15 min** (`news_poll_interval=900s`) | Poll news sources, ingest articles. |
| `sync_videos` | every **15 min** (`news_poll_interval=900s`) | Poll YouTube highlight feeds. |
| `sync_rankings` | **04:00 & 16:00** (`rankings_sync_hour=4`,16) | Sync ATP/WTA rankings. Twice daily so a single missed run doesn't bench rankings for a whole week. `misfire_grace_time=1h`. |
| `scrape_draws` | every **30 min** | Wikipedia bracket scraper — attaches/adopts draw info to match rows. `misfire_grace_time=10min`. |
| `sweep_stuck_matches` | every **1 h** | Janitor: promote/close match rows the WS forgot to finalize. |
| `sync_catalog` | **04:15** daily | Sync the full tournament catalog (brand list). |
| `enrich_player_socials` | **Tue 02:00** weekly | Walk top-200 ATP/WTA, pull socials from Wikidata (~1 player/500ms). |
| `enrich_player_bios` | **Wed 02:00** weekly | Player bios (depends on socials having populated `wikidata_ids` — runs a day after). |
| `enrich_player_images` | **Thu 02:00** weekly | Player photos (Wikipedia infobox/article + Commons category). |
| `enrich_tournaments` | every **1 h** | Wikipedia blurbs + images; up to 200 unenriched tournaments/run. |
| `enrich_tournament_dates` | every **1 day** | Formal tournament dates from Wikidata. |
| `reconcile_tournament_dates` | every **1 h** | Pull catalog start/end dates in line with observed match data when they diverge >2 days. |
| `generate_weekly_digest` | **06:00** daily | Editorial digest. Self-gates: Mondays + any Slam day publish, other days no-op. `misfire_grace_time=6h`. |
| `healthchecks_ping` | every **5 min** (`healthchecks_interval=300s`) | Heartbeat ping to Healthchecks.io. **Only registered if `healthchecks_ping_url` is set.** `misfire_grace_time=120s` to avoid false DOWN alerts on event-loop stalls. |

### Weekly-job day spread

The three weekly jobs (`enrich_player_socials`, `enrich_player_bios`,
`enrich_player_images`) are each pinned to **their own weekday at 02:00 UTC** via
`CronTrigger(day_of_week=...)`, **not** `IntervalTrigger(weeks=1)`. Interval-based
weekly jobs fire one week after the last boot, so they all bunched up within
seconds of each other on whatever day/time we last deployed — an HTTP-heavy
weekly pile-up. Pinning them **Tue → Thu** keeps at most one heavy weekly job per
day, off the 04:00–06:00 daily-cron cluster and clear of the Monday
rankings/digest rush. **`bios` deliberately runs the day after `socials`**
because it reads the `wikidata_ids` socials populates.

**Adding a new weekly job? Give it its own free weekday** (Fri–Sun are open) at
02:00 rather than stacking it on an existing day.

## Persistent background task (not a scheduled job)

- **`_live_ws_loop`** — long-lived asyncio task, not an APScheduler job. Subscribes
  to the api-tennis WebSocket for sub-second live-score updates. Self-recovers
  (REST seed + WS reconnect with exponential backoff). If WS is disabled (no key
  / no URL), falls back silently to the hourly `poll_today` REST path.

## Boot one-shots (`DateTrigger`, run once N seconds after boot)

Staggered on purpose — stacking every enrichment job in the first 90s caused a
connection-pool storm, so several boot triggers were deliberately removed and
left to their normal cadence.

| Job ID | Delay after boot |
|---|---|
| `recategorize_boot` | +1 s |
| `poll_today_boot` | +2 s |
| `sync_news_boot` | +3 s |
| `sync_videos_boot` | +6 s |
| `healthchecks_ping_boot` | +10 s (only if healthchecks configured) |
| `sweep_stuck_matches_boot` | +15 s |
| `scrape_draws_boot` | +20 s |
| `reconcile_tournament_dates_boot` | +30 s |

Jobs whose boot trigger was **intentionally removed** (daily/weekly cadence is
enough, and they were the bulk of the boot-time pool storm): `sync_rankings`,
`sync_catalog`, `enrich_player_socials`, `enrich_player_bios`,
`enrich_tournaments`, `enrich_tournament_dates`.

## Completed-match / H2H backfill — ⚠️ no scheduled job right now

This is the source of H2H history and any match that played while the box was
off. **There is currently no scheduled job filling this gap**, so expect
finished-match data to lag from whenever live ingest last ran until someone
backfills. Flagging loudly because "why is H2H missing recent meetings" traces
straight here.

- **Sackmann is dead (Jul 2026).** The `JeffSackmann/tennis_atp` and
  `tennis_wta` GitHub repos went private/were removed; every raw-CSV URL 404s.
  `scripts/sackmann_matches_ingest.py` / `sackmann_ingest.py` and the local
  `data/raw/*.csv` (frozen at May 2026) are **no longer a working source**. Do
  not rely on them.
- **Confirmed replacement: api-tennis `get_fixtures`** (the provider we already
  pay for). It serves finished matches for arbitrary past date ranges
  (`date_start`/`date_stop`, YYYY-MM-DD) back to at least 2010, in the same wire
  format our `ApiTennisProvider._map()` already parses → feed straight into
  `upsert_live_matches` (idempotent, keyed on `api_tennis_id`). A recurring
  backfill job built on this is **planned but intentionally on hold** — when
  built, give it the free **Fri** weekly slot.
- **How the current gap was last closed:** a one-time range sweep of
  `get_fixtures` (May→Jul 2026) run through `upsert_live_matches`. Until the
  recurring job exists, closing a new gap is a manual repeat of that.
