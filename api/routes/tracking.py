from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.repos import get_user_ctx

router = APIRouter()

VALID = {"new", "seen", "saved", "applied", "dismissed"}


class StatusUpdate(BaseModel):
    status: str
    snapshot: dict | None = None


@router.put("/jobs/{job_id}/status")
def set_status(job_id: str, body: StatusUpdate, ctx=Depends(get_user_ctx)) -> dict:
    if ctx is None:
        raise HTTPException(status_code=400, detail="Tracking requires the cloud backend")
    if body.status not in VALID:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID)}")
    users, user_id = ctx
    users.set_job_status(user_id, job_id, body.status, body.snapshot)
    users.record_event(user_id, "status_changed", job_id=job_id,
                       metadata={"status": body.status})
    return {"status": body.status}


@router.get("/tracked")
def tracked(ctx=Depends(get_user_ctx)) -> dict:
    if ctx is None:
        return {"tracked": []}
    users, user_id = ctx
    return {"tracked": users.get_tracked_jobs(user_id)}
