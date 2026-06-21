from fastapi import APIRouter, Depends, HTTPException

from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.services.profile_builder import build_profile

from api.deps import get_profile_extractor
from api.repos import get_scoped_repo

router = APIRouter()


def _cv_text_or_400(repo) -> str:
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    return cv["text"]


@router.get("/profile")
def get_profile(repo=Depends(get_scoped_repo)) -> ApplicantProfile:
    return repo.get_profile() or ApplicantProfile()


@router.put("/profile")
def put_profile(profile: ApplicantProfile, repo=Depends(get_scoped_repo)) -> dict:
    repo.save_profile(profile)
    return {"status": "saved"}


@router.post("/profile/extract")
def extract_profile(extractor=Depends(get_profile_extractor),
                    repo=Depends(get_scoped_repo)) -> ApplicantProfile:
    cv_text = _cv_text_or_400(repo)
    return build_profile(cv_text, extractor)
