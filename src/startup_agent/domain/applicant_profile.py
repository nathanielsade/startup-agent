from pydantic import BaseModel


class ApplicantProfile(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    location: str = ""
    current_title: str = ""
