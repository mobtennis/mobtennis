from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env — works regardless of CWD (backend/, repo root, Docker workdir).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILES = (_REPO_ROOT.parent / ".env", _REPO_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    database_url: str = "sqlite:///./data/tennismob.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    live_provider: str = "api_tennis"
    api_tennis_key: str = ""
    api_tennis_base_url: str = "https://api.api-tennis.com/tennis"
    # WebSocket endpoint — if set, the scheduler subscribes to push updates
    # instead of polling. Empty = fall back to REST polling.
    api_tennis_ws_url: str = "wss://wss.api-tennis.com/live"

    # Adaptive live polling — cadence shifts based on what's in the DB.
    # See app/jobs/scheduler.py for the decision tree.
    live_poll_live: int = 15           # ≥1 live match
    live_poll_imminent: int = 30       # match starting within imminent_horizon
    live_poll_scheduled: int = 120     # matches scheduled later today
    live_poll_idle: int = 1800         # nothing in next 24h
    live_poll_imminent_horizon: int = 900  # 15 min: how soon counts as "imminent"

    rankings_sync_hour: int = 4
    news_poll_interval: int = 900

    # Healthchecks.io push heartbeat. When set, the scheduler pings
    # this URL every `healthchecks_interval` seconds. If Healthchecks
    # doesn't hear from us within their grace period, they fire the
    # configured webhook (which on prod points at the Vercel relay →
    # Resend email). Catches "process is up but the worker loop has
    # stalled" cases that pure HTTP probing misses.
    healthchecks_ping_url: str = ""
    healthchecks_interval: int = 300  # 5 minutes

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
