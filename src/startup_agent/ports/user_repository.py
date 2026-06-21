from abc import ABC, abstractmethod

from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.domain.preferences import Preferences


class UserRepository(ABC):
    """Per-user data, keyed by the Supabase auth user id (UUID string)."""

    # CV (per user)
    @abstractmethod
    def save_cv(self, user_id: str, text: str, embedding: bytes | None, model: str) -> None: ...

    @abstractmethod
    def get_cv(self, user_id: str) -> dict | None: ...

    # Preferences (per user)
    @abstractmethod
    def save_preferences(self, user_id: str, preferences: Preferences) -> None: ...

    @abstractmethod
    def get_preferences(self, user_id: str) -> Preferences | None: ...

    # Applicant profile (per user)
    @abstractmethod
    def save_applicant_profile(self, user_id: str, profile: ApplicantProfile) -> None: ...

    @abstractmethod
    def get_applicant_profile(self, user_id: str) -> ApplicantProfile | None: ...

    # Per-job tracking + LLM cache
    @abstractmethod
    def get_job_state(self, user_id: str, job_id: str) -> dict | None: ...

    @abstractmethod
    def set_job_status(self, user_id: str, job_id: str, status: str,
                       job_snapshot: dict | None = None) -> None: ...

    @abstractmethod
    def cache_llm_score(self, user_id: str, job_id: str, score: int, reason: str) -> None: ...

    @abstractmethod
    def get_tracked_jobs(self, user_id: str) -> list[dict]: ...

    # LLM daily usage cap
    @abstractmethod
    def bump_llm_usage(self, user_id: str) -> int:
        """Increment today's LLM call count for the user; return the new total."""

    @abstractmethod
    def get_llm_usage(self, user_id: str) -> int: ...

    # Events (analytics backbone)
    @abstractmethod
    def record_event(self, user_id: str, event_type: str, job_id: str | None = None,
                     metadata: dict | None = None) -> None: ...

    @abstractmethod
    def get_events(self, user_id: str, limit: int = 500) -> list[dict]: ...
