import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class AtsType(str, Enum):
    COMEET = "comeet"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKABLE = "workable"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    UNKNOWN = "unknown"


class Company(BaseModel):
    name: str
    website: str | None = None
    careers_url: str | None = None
    ats_type: AtsType = AtsType.UNKNOWN
    ats_token: str | None = None
    sector: str | None = None
    size: str | None = None
    source: str = "snc"
    active: bool = True

    @computed_field
    @property
    def id_hash(self) -> str:
        return hashlib.sha256(self.name.encode()).hexdigest()[:16]


class RawJob(BaseModel):
    """Provider-shaped job as returned by an ATS, pre-normalization."""
    ats_job_id: str
    payload: dict


class Job(BaseModel):
    company_id: str
    ats_job_id: str
    title: str
    url: str
    location: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    first_seen_at: datetime | None = None

    @computed_field
    @property
    def id(self) -> str:
        raw = f"{self.company_id}:{self.ats_job_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MatchResult(BaseModel):
    job_id: str
    score: int = Field(ge=0, le=100)
    reason: str
    stage: str


class RunReport(BaseModel):
    companies_count: int = 0
    jobs_fetched: int = 0
    jobs_new: int = 0
    jobs_matched: int = 0
    status: str = "success"
    error: str | None = None
