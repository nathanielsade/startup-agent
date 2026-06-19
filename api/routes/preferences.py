from fastapi import APIRouter, Depends

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.preferences import Preferences

from api.deps import get_settings

router = APIRouter()


@router.get("/preferences")
def get_preferences(settings=Depends(get_settings)) -> Preferences:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    return repo.get_preferences() or Preferences()


@router.put("/preferences")
def put_preferences(prefs: Preferences, settings=Depends(get_settings)) -> dict:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.save_preferences(prefs)
    return {"status": "saved"}
