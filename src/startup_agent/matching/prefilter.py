from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.location import location_allowed


def passes_prefilter(job: Job, preferences: Preferences) -> bool:
    title = job.title.lower()
    if any(term.lower() in title for term in preferences.exclude):
        return False
    if preferences.title_include and not any(
        term.lower() in title for term in preferences.title_include
    ):
        return False
    if not location_allowed(job.location):
        return False
    return True
