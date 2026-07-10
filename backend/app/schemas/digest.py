from datetime import date, datetime

from pydantic import BaseModel


class DigestSummary(BaseModel):
    """List-card shape. No body — keeps the archive list small."""
    week_start: date
    headline: str
    generated_at: datetime


class NewsSource(BaseModel):
    """A single news article the LLM cited while writing the digest.

    The recap paraphrases off-court news (injuries, withdrawals, press
    conferences). When the body leans on a specific headline, we render
    a link to the original article so readers can read further and we
    visibly credit the upstream publisher.
    """
    title: str
    url: str
    source: str  # publisher name, e.g. "Reuters", "tennis.com"


class DigestImage(BaseModel):
    """An inline article image. Sourced from a news-wire share photo
    (credited + linked back to the publisher) or a licensed player
    Commons photo. `anchor` places it: "lead" above the prose, "mid"
    interleaved into it."""
    url: str
    credit: str | None = None
    credit_url: str | None = None
    caption: str | None = None
    anchor: str = "lead"


class DigestDetail(DigestSummary):
    body_md: str
    model_name: str
    news_sources: list[NewsSource] = []
    images: list[DigestImage] = []
    # Coverage window the digest actually summarised. Nullable for
    # backfilled legacy rows that pre-date the period tracking —
    # those covered the ISO week starting at `week_start`.
    period_start: datetime | None = None
    period_end: datetime | None = None


class CampaignBrief(BaseModel):
    """One Google Ads campaign suggestion produced by Claude alongside
    the weekly digest. The operator hand-launches the campaign in the
    Google Ads UI using these as a brief. Constrained to Google Ads
    Responsive Search Ad limits so a paste straight into the UI fits."""
    theme: str                  # short label, e.g. "Alcaraz Wimbledon withdrawal"
    rationale: str              # 1-2 sentences explaining the search-interest hypothesis
    keywords: list[str]         # 5-15 search terms, each ≤ 80 chars
    ad_headlines: list[str]     # 3-15 RSA headlines, each ≤ 30 chars
    ad_descriptions: list[str]  # 2-4 RSA descriptions, each ≤ 90 chars
    landing_path: str           # internal mob.tennis path, starts with "/"


class CampaignBriefsResponse(BaseModel):
    """Admin endpoint payload — the briefs plus the digest metadata that
    contextualises them."""
    week_start: date
    headline: str
    generated_at: datetime
    briefs: list[CampaignBrief]
