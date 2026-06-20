from datetime import datetime, timedelta, timezone

import structlog

from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

from api.schemas import JobMatch, job_match_from_result, to_job_match

logger = structlog.get_logger()


def _is_recent(job: Job, now: datetime, recent_hours: int) -> bool:
    if job.posted_at is None:
        return False
    return (now - job.posted_at.astimezone(timezone.utc)) <= timedelta(hours=recent_hours)


def rescore_recent(pairs: list[tuple[Job, float]], ranker, cv_text: str,
                   preferences: Preferences, recent_hours: int,
                   company_names: dict[str, str], now: datetime | None = None,
                   company_links: dict[str, str | None] | None = None) -> list[JobMatch]:
    now = now or datetime.now(timezone.utc)
    rated: list[JobMatch] = []
    unrated: list[JobMatch] = []
    for job, score in pairs:
        if _is_recent(job, now, recent_hours):
            try:
                result = ranker.rank(cv_text, [job], preferences)[0]
                rated.append(job_match_from_result(job, result, company_names, now, company_links))
                continue
            except Exception as error:  # keep embedding score on failure
                logger.warning("rate_failed", job=job.title, error=str(error))
        unrated.append(to_job_match(job, score, company_names, now, company_links))
    rated.sort(key=lambda m: m.score, reverse=True)
    unrated.sort(key=lambda m: m.score, reverse=True)
    return rated + unrated
