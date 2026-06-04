from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# Repo-root /data — independent of CWD so backend works whether started from
# `backend/`, repo root, or a Docker workdir.
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_database_url(url: str) -> str:
    """For sqlite URLs with a relative path, rewrite to an absolute repo-root path."""
    if not url.startswith("sqlite"):
        return url
    # sqlite:/// (3 slashes = relative) or sqlite://// (4 = absolute)
    prefix, _, path = url.partition("sqlite:///")
    if not path or path.startswith("/"):
        return url
    rel = path.lstrip("./")
    abs_path = (DATA_DIR / Path(rel).name).resolve()
    return f"sqlite:///{abs_path}"


DATABASE_URL = _resolve_database_url(settings.database_url)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# SQLite's default pool (5 + 10 overflow) was sized for client-server DBs;
# in WAL mode SQLite is happy with many connections (one writer at a
# time, many concurrent readers). The pool maxing out caused 30s checkout
# timeouts under bursty Vercel SSR fan-out + the WS consumer + scheduled
# jobs all wanting connections simultaneously. Larger pool = less queueing.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)


# SQLite tuning. Without these, a single in-flight write blocks every reader
# and the SQLAlchemy connection pool fills up: a recurring outage symptom we
# saw in prod where the live-WS consumer's tournament upsert held the writer
# lock long enough to time out 11 simultaneous /api/tournaments/index reads.
#   journal_mode=WAL      — readers run concurrently with the single writer
#   busy_timeout=5000     — writers wait up to 5s for the lock instead of
#                           failing immediately with "database is locked"
#   synchronous=NORMAL    — safe under WAL, ~2× faster commits than FULL
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def init_db() -> None:
    from app import models  # noqa: F401  — register tables

    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Hand-rolled column additions for an existing SQLite DB.

    SQLModel.metadata.create_all only creates *missing* tables — it doesn't
    alter existing ones. New nullable columns are safe to add via ALTER TABLE
    in SQLite, so we do that here. Idempotent.
    """
    from sqlalchemy import text

    pending: list[tuple[str, str, str]] = [
        # (table, column, ddl)
        ("tournaments", "description", "TEXT"),
        ("tournaments", "image_url", "TEXT"),
        ("tournaments", "wikipedia_url", "TEXT"),
        ("tournaments", "enriched_at", "DATETIME"),
        ("follows", "target_tour", "TEXT"),
        ("players", "wikidata_id", "TEXT"),
        ("players", "wikipedia_url", "TEXT"),
        ("players", "instagram_handle", "TEXT"),
        ("players", "twitter_handle", "TEXT"),
        ("players", "instagram_latest_post_url", "TEXT"),
        ("players", "socials_enriched_at", "DATETIME"),
        ("players", "bio_enriched_at", "DATETIME"),
        ("players", "name_key", "TEXT"),
        ("players", "image_source", "TEXT"),
        ("players", "image_credit", "TEXT"),
        ("players", "image_license_url", "TEXT"),
        ("players", "hero_image_url", "TEXT"),
        ("player_images", "is_hero", "INTEGER DEFAULT 0"),
        ("player_images", "is_hero_eligible", "INTEGER DEFAULT 0"),
        # spot_the_ball_puzzles is created by create_all on first run;
        # no per-column migration needed for the initial release.
        ("matches", "stats_json", "TEXT"),
        ("matches", "bracket_position", "INTEGER"),
        ("matches", "player1_seed", "INTEGER"),
        ("matches", "player2_seed", "INTEGER"),
        ("video_items", "is_portrait", "INTEGER"),
        ("editorial_digests", "campaign_briefs_json", "TEXT"),
        ("editorial_digests", "period_start", "DATETIME"),
        ("editorial_digests", "period_end", "DATETIME"),
    ]

    with engine.begin() as conn:
        for table, column, ddl in pending:
            cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    # rankings(player_id, tour, week) unique index. Existing duplicates
    # (introduced by earlier merge_duplicates passes that didn't dedupe
    # ranking rows) need to be collapsed before the index can be created.
    _ensure_rankings_unique_index()


def _ensure_rankings_unique_index() -> None:
    """Idempotent: if the unique index isn't present, dedupe any
    existing duplicate ranking rows then create it. Runs once per
    fresh process; subsequent calls become near-no-ops."""
    from sqlalchemy import text

    with engine.begin() as conn:
        existing = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_rankings_player_tour_week'"
        )).first()
        if existing:
            return

        # Keep the row with the lowest rank for each (player, tour, week).
        # Ties broken by lowest id. The other rows are deleted.
        conn.execute(text("""
            DELETE FROM rankings
            WHERE id IN (
              SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                         PARTITION BY player_id, tour, week
                         ORDER BY rank ASC, id ASC
                       ) AS rn
                FROM rankings
              )
              WHERE rn > 1
            )
        """))
        conn.execute(text(
            "CREATE UNIQUE INDEX uq_rankings_player_tour_week "
            "ON rankings (player_id, tour, week)"
        ))


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
