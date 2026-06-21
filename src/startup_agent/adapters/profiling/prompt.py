from startup_agent.domain.applicant_profile import ApplicantProfile

INSTRUCTIONS = (
    "You read a candidate's CV and extract ONLY these fields: "
    "first_name, last_name, location (city, country), current_title "
    "(their most recent or current job title), and years_experience "
    "(their total years of professional experience as a whole number; null if unclear). "
    "Do NOT extract email, phone, or URLs. "
    'Return JSON: {"first_name": "", "last_name": "", "location": "", '
    '"current_title": "", "years_experience": null}.'
)

_TEXT_FIELDS = ("first_name", "last_name", "location", "current_title")


def to_profile(data: dict) -> ApplicantProfile:
    """Build an ApplicantProfile holding ONLY the LLM judgment fields."""
    fields = {k: str(data.get(k) or "") for k in _TEXT_FIELDS}
    years = data.get("years_experience")
    fields["years_experience"] = years if isinstance(years, int) and years >= 0 else None
    return ApplicantProfile(**fields)
