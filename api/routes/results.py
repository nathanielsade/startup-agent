from fastapi import APIRouter, Depends

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository

from api.deps import get_embedder, get_settings
from api.matching_view import compute_matches

router = APIRouter()


@router.get("/results")
def results(embedder=Depends(get_embedder), settings=Depends(get_settings)) -> dict:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    if repo.get_cv() is None:
        return {"matches": []}
    matches = compute_matches(repo, embedder, settings.preferences_path,
                              settings.match_threshold)
    return {"matches": [m.model_dump() for m in matches]}
