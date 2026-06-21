from datetime import datetime, timezone

from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.location import region_allowed


def passes_prefilter(job: Job, preferences: Preferences,
                     now: datetime | None = None) -> bool:
    title = job.title.lower()

    # title exclude / include
    if any(term.lower() in title for term in preferences.exclude):
        return False
    if preferences.title_include and not any(
        term.lower() in title for term in preferences.title_include
    ):
        return False

    # district / remote
    if not region_allowed(job.location, set(preferences.districts), preferences.include_remote):
        return False

    # freshness
    if preferences.posted_within_days is not None and job.posted_at is not None:
        now = now or datetime.now(timezone.utc)
        age_days = (now - job.posted_at.astimezone(timezone.utc)).days
        if age_days > preferences.posted_within_days:
            return False

    return True
