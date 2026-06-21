import html as _html
import re
from datetime import datetime, timezone

from pydantic import BaseModel

from startup_agent.domain.models import Job, MatchResult

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _plain_text(text: str | None, cap: int = 1200) -> str | None:
    """Strip HTML tags, unescape entities, collapse whitespace, truncate."""
    if not text:
        return None
    clean = _WS.sub(" ", _html.unescape(_TAGS.sub(" ", text))).strip()
    if not clean:
        return None
    return clean[:cap].rstrip() + "…" if len(clean) > cap else clean


class JobMatch(BaseModel):
    job_id: str
    title: str
    company: str
    location: str | None
    score: int
    url: str
    posted_at: str | None
    age_label: str
    reason: str | None = None
    rated: bool = False
    ai_scored: bool = False
    company_linkedin_url: str | None = None
    company_website: str | None = None
    description: str | None = None
    status: str = "new"   # per-user tracking: new|seen|saved|applied|dismissed


def _age_label(posted_at: datetime | None, now: datetime) -> str:
    if not posted_at:
        return ""
    delta = now - posted_at.astimezone(timezone.utc)
    if delta.days >= 1:
        return f"{delta.days}d ago"
    return f"{int(delta.seconds // 3600)}h ago"


def to_job_match(job: Job, score: float, company_names: dict[str, str],
                 now: datetime | None = None,
                 company_links: dict[str, str | None] | None = None,
                 company_websites: dict[str, str | None] | None = None) -> JobMatch:
    now = now or datetime.now(timezone.utc)
    return JobMatch(
        job_id=job.id,
        title=job.title,
        company=company_names.get(job.company_id, "?"),
        location=job.location,
        score=int(score * 100),
        url=job.url,
        posted_at=job.posted_at.isoformat() if job.posted_at else None,
        age_label=_age_label(job.posted_at, now),
        company_linkedin_url=(company_links or {}).get(job.company_id),
        company_website=(company_websites or {}).get(job.company_id),
        description=_plain_text(job.description),
    )


def job_match_from_result(job: Job, result: MatchResult, company_names: dict[str, str],
                          now: datetime | None = None,
                          company_links: dict[str, str | None] | None = None,
                          company_websites: dict[str, str | None] | None = None) -> JobMatch:
    base = to_job_match(job, 0.0, company_names, now, company_links, company_websites)
    return base.model_copy(update={"score": result.score, "reason": result.reason,
                                   "rated": True, "ai_scored": True})
