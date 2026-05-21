from datetime import date, datetime

from pydantic import BaseModel


class DigestSummary(BaseModel):
    """List-card shape. No body — keeps the archive list small."""
    week_start: date
    headline: str
    generated_at: datetime


class DigestDetail(DigestSummary):
    body_md: str
    model_name: str


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
