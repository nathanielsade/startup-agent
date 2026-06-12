from abc import ABC, abstractmethod

from startup_agent.domain.models import Job, MatchResult


class Ranker(ABC):
    @abstractmethod
    def rank(self, cv_text: str, jobs: list[Job]) -> list[MatchResult]: ...
