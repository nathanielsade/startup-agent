from startup_agent.domain.applicant_profile import ApplicantProfile

INSTRUCTIONS = (
    "You read a candidate's CV and extract ONLY these identity fields: "
    "first_name, last_name, location (city, country), and current_title "
    "(their most recent or current job title). "
    "Do NOT extract email, phone, or URLs. "
    'Return JSON: {"first_name": "", "last_name": "", "location": "", "current_title": ""}.'
)

_JUDGMENT = ("first_name", "last_name", "location", "current_title")


def to_profile(data: dict) -> ApplicantProfile:
    """Build an ApplicantProfile holding ONLY the LLM judgment fields (str-coerced)."""
    fields = {k: str(data.get(k) or "") for k in _JUDGMENT}
    return ApplicantProfile(**fields)
