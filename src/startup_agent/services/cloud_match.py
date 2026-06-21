from datetime import datetime, timedelta, timezone

import structlog

from startup_agent.domain.models import MatchResult
from startup_agent.matching.experience import inferred_required_years
from startup_agent.matching.experience_fit import experience_penalty
from startup_agent.matching.location import Region, classify_location
from startup_agent.ports.embedder import Embedder
from startup_agent.services.matching import SimilarityMatchingService

from api.schemas import job_match_from_result, to_job_match

logger = structlog.get_logger()

_DNAME = {Region.CENTER: "center", Region.NORTH: "north",
          Region.SOUTH: "south", Region.JERUSALEM: "jerusalem"}


def _district_name(location):
    return _DNAME.get(classify_location(location))


def _is_recent(job, now, recent_hours):
    if job.posted_at is None:
        return False
    return (now - job.posted_at.astimezone(timezone.utc)) <= timedelta(hours=recent_hours)


def match_for_user(scoped_repo, user_repo, user_id: str, embedder: Embedder,
                   preferences_path: str, threshold: float, *, ranker=None,
                   cap: int = 60, recent_hours: int = 24, top_n: int = 25,
                   now: datetime | None = None) -> list:
    """Recall (embedding) -> rerank (LLM from rank card) -> experience penalty.

    Candidates = top_n by cosine ∪ posted in last `recent_hours`. Cached LLM scores
    are reused; fresh candidates are scored until the daily `cap`. A deterministic
    experience-gap penalty (and a small max_years over-cap penalty) is applied in
    code; non-candidates fall through with their embedding score (ai_scored=False).
    """
    from api.matching_view import _load_prefs

    prefs = _load_prefs(scoped_repo, preferences_path)
    pairs = SimilarityMatchingService(repo=scoped_repo, embedder=embedder,
                                      preferences=prefs, threshold=threshold).run()
    cv = scoped_repo.get_cv()
    cv_text = cv["text"] if cv else ""
    profile = scoped_repo.get_profile()
    user_years = profile.years_experience if profile else None
    companies = scoped_repo.get_companies()
    names = {c.id_hash: c.name for c in companies}
    links = {c.id_hash: c.linkedin_url for c in companies}
    sites = {c.id_hash: c.website for c in companies}
    now = now or datetime.now(timezone.utc)
    used = user_repo.get_llm_usage(user_id)

    candidate_ids = {job.id for job, _ in pairs[:top_n]}
    candidate_ids |= {job.id for job, _ in pairs if _is_recent(job, now, recent_hours)}

    out = []
    for job, score in pairs:
        cached = user_repo.get_job_state(user_id, job.id)
        ai_score, reason = None, ""
        if cached and cached.get("llm_score") is not None:
            ai_score, reason = cached["llm_score"], cached.get("llm_reason") or ""
        elif job.id in candidate_ids and ranker is not None and used < cap:
            try:
                card = scoped_repo.get_rank_card(job.id)
                r = ranker.rank_one(cv_text, job, prefs, card=card,
                                    district=_district_name(job.location))
                user_repo.cache_llm_score(user_id, job.id, r.score, r.reason)
                used = user_repo.bump_llm_usage(user_id)
                ai_score, reason = r.score, r.reason
            except Exception as error:  # noqa: BLE001 - keep embedding score on failure
                logger.warning("llm_rank_failed", job=job.title, error=str(error))

        if ai_score is not None:
            card = scoped_repo.get_rank_card(job.id) or {}
            req = inferred_required_years(job.title, job.description,
                                          card.get("required_years"))
            penalty = experience_penalty(user_years, req)
            if prefs.max_years is not None and req is not None and req > prefs.max_years:
                penalty += 10
            final = max(0, min(100, ai_score - penalty))
            note = (f" · needs ~{req} yrs vs your {user_years}"
                    if penalty and user_years is not None and req is not None else "")
            mr = MatchResult(job_id=job.id, score=final, reason=(reason + note), stage="llm")
            jm = job_match_from_result(job, mr, names, now, links, sites)
        else:
            jm = to_job_match(job, score, names, now, links, sites)

        if cached and cached.get("status"):
            jm = jm.model_copy(update={"status": cached["status"]})
        out.append(jm)

    out.sort(key=lambda m: (m.ai_scored, m.score), reverse=True)
    user_repo.record_event(user_id, "search_run",
                           metadata={"matched": len(out), "llm_used_today": used})
    return out
