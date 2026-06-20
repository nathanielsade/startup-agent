from fastapi import APIRouter, Depends, HTTPException

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.services.profile_builder import build_profile

from api.deps import get_profile_extractor, get_settings

router = APIRouter()


def _cv_text_or_400(repo) -> str:
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    return cv["text"]


@router.get("/profile")
def get_profile(settings=Depends(get_settings)) -> ApplicantProfile:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    return repo.get_profile() or ApplicantProfile()


@router.put("/profile")
def put_profile(profile: ApplicantProfile, settings=Depends(get_settings)) -> dict:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.save_profile(profile)
    return {"status": "saved"}


@router.post("/profile/extract")
def extract_profile(extractor=Depends(get_profile_extractor),
                    settings=Depends(get_settings)) -> ApplicantProfile:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    cv_text = _cv_text_or_400(repo)
    return build_profile(cv_text, extractor)
