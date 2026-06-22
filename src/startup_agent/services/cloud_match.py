from concurrent.futures import ThreadPoolExecutor, as_completed
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

_RERANK_WORKERS = 8   # concurrent LLM rerank calls (HTTP-bound; OpenAI client is thread-safe)

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

    # Read per-user state + rank cards up front (main thread only — psycopg is not
    # safe for concurrent use). Cards fetched once and reused for scoring + penalty.
    states = {job.id: user_repo.get_job_state(user_id, job.id) for job, _ in pairs}
    cards = {job.id: scoped_repo.get_rank_card(job.id)
             for job, _ in pairs if job.id in candidate_ids}

    def _is_cached(job_id: str) -> bool:
        st = states[job_id]
        return bool(st and st.get("llm_score") is not None)

    # candidates needing a fresh score, top-cosine first, capped to the daily budget
    need = [job for job, _ in pairs
            if job.id in candidate_ids and ranker is not None and not _is_cached(job.id)]
    need = need[:max(0, cap - used)]

    # score them concurrently — each thread only does the LLM HTTP call (no DB)
    fresh: dict[str, MatchResult] = {}
    if need:
        with ThreadPoolExecutor(max_workers=_RERANK_WORKERS) as pool:
            futures = {pool.submit(ranker.rank_one, cv_text, job, prefs,
                                   cards.get(job.id), _district_name(job.location)): job
                       for job in need}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    fresh[job.id] = future.result()
                except Exception as error:  # noqa: BLE001 - keep embedding score on failure
                    logger.warning("llm_rank_failed", job=job.title, error=str(error))

    # persist fresh scores sequentially (DB writes back on the main thread)
    for job in need:
        result = fresh.get(job.id)
        if result is not None:
            user_repo.cache_llm_score(user_id, job.id, result.score, result.reason)
            used = user_repo.bump_llm_usage(user_id)

    out = []
    for job, score in pairs:
        cached = states[job.id]
        ai_score, reason = None, ""
        if cached and cached.get("llm_score") is not None:
            ai_score, reason = cached["llm_score"], cached.get("llm_reason") or ""
        elif job.id in fresh:
            ai_score, reason = fresh[job.id].score, fresh[job.id].reason

        if ai_score is not None:
            card = cards.get(job.id) or {}
            req = inferred_required_years(job.title, job.description,
                                          card.get("required_years"))
            penalty = experience_penalty(user_years, req)
            if prefs.max_years is not None and req is not None and req > prefs.max_years:
                penalty += 10
            final = max(0, min(100, ai_score - penalty))
            # the 2-3 sentence LLM reason already covers skills/experience fit + gap
            mr = MatchResult(job_id=job.id, score=final, reason=reason, stage="llm")
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
