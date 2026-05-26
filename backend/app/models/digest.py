"""Editorial digest — one paragraph of human-readable narrative covering
both tours for a window of tennis news.

Originally one-per-week (Monday cron). Now also supports ad-hoc
mid-week generation when big news lands. Each row covers
`[period_start, period_end]` rather than a fixed calendar week, and
the natural sliding-window logic in `services/editorial_digest.py`
picks the right span based on the previous digest's `period_end`.

The `week_start` column is retained as the URL slug ("anchor date")
to keep existing /digest/<date> URLs working. For new digests it's
the date the LLM call ran on; for backfilled / pre-windowed rows
it's the Monday of the covered week. The unique constraint stays so
the 24h rate-limit + same-day reruns are caught at the DB level too.

Stored once, served from cache (no per-request LLM call). Generated
by the cron job in `app/jobs/scheduler.py`, the backfill script in
`scripts/backfill_digests.py`, and an ad-hoc admin trigger.
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class EditorialDigest(SQLModel, table=True):
    __tablename__ = "editorial_digests"

    id: int | None = Field(default=None, primary_key=True)

    # Anchor date / URL slug. For Monday cron runs this is the Monday
    # the digest was published on; for ad-hoc generations it's the
    # date the LLM call ran. Unique so we can't accidentally produce
    # two digests for the same calendar day — the 24h rate-limit gate
    # is the primary check; this is the belt-and-suspenders.
    week_start: date = Field(index=True, unique=True)

    # Coverage window the digest summarises. Defaulted to
    # last_digest.period_end → now by the generator, so a Wednesday
    # ad-hoc run produces a digest that covers "since the last digest"
    # not "the past 7 days". Nullable for backfill of legacy rows
    # which had no explicit window (those covered the ISO week
    # starting at `week_start`).
    period_start: datetime | None = None
    period_end: datetime | None = None

    headline: str
    body_md: str

    # JSON-serialised dump of the structured facts we fed the model.
    # Kept for audit and for re-runs against an updated prompt without
    # re-querying the DB.
    source_json: str

    # JSON-serialised list of Google Ads campaign briefs produced
    # alongside the digest. Each entry has a theme, keyword list, ad
    # headlines, descriptions, and a landing URL on mob.tennis.
    # Surfaced on /admin/campaigns/<week> for the human operator to
    # copy-paste into Google Ads UI. Null on backfilled digests that
    # predate this feature.
    campaign_briefs_json: str | None = None

    # Provider model id at time of generation. Useful when we eventually
    # swap models — old rows stay attributable to the model that wrote
    # them.
    model_name: str

    generated_at: datetime = Field(default_factory=datetime.utcnow)
