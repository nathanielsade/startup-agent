from fastapi import APIRouter, Depends, HTTPException

from startup_agent.domain.preferences import Preferences

from api.deps import get_suggester
from api.repos import get_scoped_repo

router = APIRouter()


@router.get("/preferences")
def get_preferences(repo=Depends(get_scoped_repo)) -> Preferences:
    return repo.get_preferences() or Preferences()


@router.put("/preferences")
def put_preferences(prefs: Preferences, repo=Depends(get_scoped_repo)) -> dict:
    repo.save_preferences(prefs)
    return {"status": "saved"}


@router.post("/preferences/suggest")
def suggest_preferences(suggester=Depends(get_suggester),
                        repo=Depends(get_scoped_repo)) -> Preferences:
    if suggester is None:
        raise HTTPException(status_code=400, detail="No LLM configured. Add a key in AI scoring.")
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    current = repo.get_preferences() or Preferences()
    try:
        suggestion = suggester.suggest(cv["text"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Auto-fill failed, please try again.") from exc
    # Clear title_include — it's a hard prefilter the UI doesn't expose, so an
    # auto-filled value (e.g. "Backend Software Engineer") silently filters out
    # almost every job. Setting it to [] also heals stale values on re-run.
    # Roles/seniority capture role intent instead.
    return current.model_copy(update={
        "max_years": suggestion.max_years,
        "roles": suggestion.roles,
        "seniority": suggestion.seniority,
        "title_include": [],
    })
