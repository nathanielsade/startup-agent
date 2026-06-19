from abc import ABC, abstractmethod

from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences


class Ranker(ABC):
    @abstractmethod
    def rank(self, cv_text: str, jobs: list[Job],
             preferences: Preferences | None = None) -> list[MatchResult]: ...
