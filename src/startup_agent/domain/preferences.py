from pydantic import BaseModel, Field


class Preferences(BaseModel):
    # hard filters
    districts: list[str] = Field(default_factory=list)        # center/north/south/jerusalem; [] = no constraint
    include_remote: bool = True
    max_years: int | None = None                              # None = no limit
    posted_within_days: int | None = None                     # None = no limit
    title_include: list[str] = Field(default_factory=list)    # title must contain one (if set)
    exclude: list[str] = Field(default_factory=list)          # title must not contain any
    # soft signals (rank only)
    roles: list[str] = Field(default_factory=list)            # domain keywords: backend/ai/data/...
    seniority: list[str] = Field(default_factory=list)        # junior/mid/senior
    # legacy/unused (kept for yaml-loader compatibility)
    locations: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
