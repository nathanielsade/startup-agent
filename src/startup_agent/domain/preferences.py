from pydantic import BaseModel, Field


class Preferences(BaseModel):
    roles: list[str] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    title_include: list[str] = Field(default_factory=list)
