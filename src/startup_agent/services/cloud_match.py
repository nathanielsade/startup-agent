from datetime import datetime, timedelta, timezone

import structlog

from startup_agent.domain.models import Job, MatchResult
from startup_agent.ports.embedder import Embedder
from startup_agent.services.matching import SimilarityMatchingService

from api.schemas import job_match_from_result, to_job_match

logger = structlog.get_logger()


def _is_recent(job: Job, now: datetime, recent_hours: int) -> bool:
    if job.posted_at is None:
        return False
    return (now - job.posted_at.astimezone(timezone.utc)) <= timedelta(hours=recent_hours)


def match_for_user(scoped_repo, user_repo, user_id: str, embedder: Embedder,
                   preferences_path: str, threshold: float, *, ranker=None,
                   cap: int = 30, recent_hours: int = 24, now: datetime | None = None) -> list:
    """Per-user matching over precomputed job vectors, plus capped auto-LLM rerank.

    - Embedding match (free) ranks all jobs using the batch-precomputed vectors.
    - Cached LLM scores (from prior runs) are reused — never re-paid.
    - Each user's freshest (last `recent_hours`) un-scored jobs are LLM-ranked up to a
      daily `cap`; scores are cached and usage is counted. Logs a `search_run` event.
    """
    from api.matching_view import _load_prefs

    prefs = _load_prefs(scoped_repo, preferences_path)
    pairs = SimilarityMatchingService(repo=scoped_repo, embedder=embedder,
                                      preferences=prefs, threshold=threshold).run()
    cv = scoped_repo.get_cv()
    cv_text = cv["text"] if cv else ""
    companies = scoped_repo.get_companies()
    names = {c.id_hash: c.name for c in companies}
    links = {c.id_hash: c.linkedin_url for c in companies}
    sites = {c.id_hash: c.website for c in companies}
    now = now or datetime.now(timezone.utc)
    used = user_repo.get_llm_usage(user_id)

    out = []
    for job, score in pairs:
        cached = user_repo.get_job_state(user_id, job.id)
        if cached and cached.get("llm_score") is not None:
            r = MatchResult(job_id=job.id, score=cached["llm_score"],
                            reason=cached.get("llm_reason") or "", stage="llm")
            out.append(job_match_from_result(job, r, names, now, links, sites))
        elif ranker is not None and used < cap and _is_recent(job, now, recent_hours):
            try:
                r = ranker.rank(cv_text, [job], prefs)[0]
                user_repo.cache_llm_score(user_id, job.id, r.score, r.reason)
                used = user_repo.bump_llm_usage(user_id)
                out.append(job_match_from_result(job, r, names, now, links, sites))
            except Exception as error:
                logger.warning("llm_rank_failed", job=job.title, error=str(error))
                out.append(to_job_match(job, score, names, now, links, sites))
        else:
            out.append(to_job_match(job, score, names, now, links, sites))

    out.sort(key=lambda m: m.score, reverse=True)
    user_repo.record_event(user_id, "search_run", metadata={"matched": len(out),
                                                            "llm_used_today": used})
    return out
