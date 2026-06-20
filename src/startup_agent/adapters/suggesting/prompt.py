from startup_agent.domain.preferences import Preferences

ROLE_VOCAB = ["backend", "frontend", "full-stack", "ai", "data", "devops", "security"]
SENIORITY_VOCAB = ["junior", "mid", "senior"]

INSTRUCTIONS = (
    "You read a candidate's CV and infer ONLY what the CV actually reveals: "
    "a sensible maximum years-of-experience to target (an integer), the role/domain(s), "
    "the seniority level, and relevant job-title keywords. "
    f"roles MUST be chosen from: {ROLE_VOCAB}. "
    f"seniority MUST be chosen from: {SENIORITY_VOCAB}. "
    "Do NOT infer location, district, or remote preferences. "
    'Return JSON: {"max_years": <int>, "roles": [...], "seniority": [...], "title_include": [...]}.'
)


def to_preferences(data: dict) -> Preferences:
    """Validate a raw suggestion dict into a Preferences (inferable fields only)."""
    roles = [r for r in (data.get("roles") or []) if r in ROLE_VOCAB]
    seniority = [s for s in (data.get("seniority") or []) if s in SENIORITY_VOCAB]
    title_include = [str(t) for t in (data.get("title_include") or [])]
    max_years = data.get("max_years")
    if max_years is not None:
        try:
            max_years = int(max_years)
        except (ValueError, TypeError):
            max_years = None
    return Preferences(max_years=max_years, roles=roles, seniority=seniority,
                       title_include=title_include)
