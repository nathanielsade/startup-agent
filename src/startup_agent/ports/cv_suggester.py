from abc import ABC, abstractmethod

from startup_agent.domain.preferences import Preferences


class CvPreferenceSuggester(ABC):
    @abstractmethod
    def suggest(self, cv_text: str) -> Preferences: ...
