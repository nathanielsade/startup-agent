from fastapi import APIRouter, Depends

from startup_agent.adapters.storage.user_scoped import UserScopedRepository

from api.deps import get_embedder, get_ranker, get_rerank_ranker, get_settings
from api.matching_view import compute_matches
from api.repos import get_scoped_repo

router = APIRouter()


@router.get("/results")
def results(repo=Depends(get_scoped_repo), embedder=Depends(get_embedder),
            ranker=Depends(get_ranker), settings=Depends(get_settings)) -> dict:
    if repo.get_cv() is None:
        return {"matches": []}
    if isinstance(repo, UserScopedRepository):
        # cloud: per-user match over precomputed vectors + capped auto-LLM rerank
        from startup_agent.services.cloud_match import match_for_user
        matches = match_for_user(repo, repo.users, repo.user_id, embedder,
                                 settings.preferences_path, settings.match_threshold,
                                 ranker=get_rerank_ranker(), cap=settings.llm_daily_cap,
                                 recent_hours=settings.llm_recent_hours)
    else:
        # local single-tenant: embedding match only
        matches = compute_matches(repo, embedder, settings.preferences_path,
                                  settings.match_threshold)
    return {"matches": [m.model_dump() for m in matches]}
