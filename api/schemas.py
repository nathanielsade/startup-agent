from datetime import datetime, timezone

from pydantic import BaseModel

from startup_agent.domain.models import Job, MatchResult


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
    company_linkedin_url: str | None = None


def _age_label(posted_at: datetime | None, now: datetime) -> str:
    if not posted_at:
        return ""
    delta = now - posted_at.astimezone(timezone.utc)
    if delta.days >= 1:
        return f"{delta.days}d ago"
    return f"{int(delta.seconds // 3600)}h ago"


def to_job_match(job: Job, score: float, company_names: dict[str, str],
                 now: datetime | None = None,
                 company_links: dict[str, str | None] | None = None) -> JobMatch:
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
    )


def job_match_from_result(job: Job, result: MatchResult, company_names: dict[str, str],
                          now: datetime | None = None,
                          company_links: dict[str, str | None] | None = None) -> JobMatch:
    base = to_job_match(job, 0.0, company_names, now, company_links)
    return base.model_copy(update={"score": result.score, "reason": result.reason,
                                   "rated": True})
