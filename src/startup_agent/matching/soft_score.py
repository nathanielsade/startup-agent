from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

_ROLE_BONUS = 0.05
_SENIORITY_PENALTY = 0.05
_SENIOR_MARKERS = ("senior", "staff", "principal", "lead", "director")


def soft_adjust(job: Job, preferences: Preferences, base: float) -> float:
    text = f"{job.title} {job.description or ''}".lower()
    score = base

    if preferences.roles and any(role.lower() in text for role in preferences.roles):
        score += _ROLE_BONUS

    # if user wants junior/mid only and the job reads senior, nudge down
    wants_junior = any(s.lower() in ("junior", "mid", "entry", "associate")
                       for s in preferences.seniority)
    if wants_junior and any(marker in text for marker in _SENIOR_MARKERS):
        score -= _SENIORITY_PENALTY

    return score
