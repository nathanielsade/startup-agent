from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository

from api.deps import get_ranker, get_settings
from api.matching_view import _load_prefs


class RateRequest(BaseModel):
    job_id: str


router = APIRouter()


@router.post("/rate")
def rate(body: RateRequest, ranker=Depends(get_ranker), settings=Depends(get_settings)) -> dict:
    if ranker is None:
        raise HTTPException(status_code=400, detail="No LLM configured. Add a key to .env.")
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    job = repo.get_job(body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    prefs = _load_prefs(repo, settings.preferences_path)
    result = ranker.rank(cv["text"], [job], prefs)[0]
    return {"score": result.score, "reason": result.reason}
