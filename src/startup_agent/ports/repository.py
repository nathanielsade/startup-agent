from abc import ABC, abstractmethod

from startup_agent.domain.models import Company, Job, MatchResult, RunReport
from startup_agent.domain.preferences import Preferences


class JobRepository(ABC):
    @abstractmethod
    def upsert_company(self, company: Company) -> str: ...

    @abstractmethod
    def get_companies(self, active_only: bool = True) -> list[Company]: ...

    @abstractmethod
    def upsert_job(self, job: Job) -> bool:
        """Returns True if the job is new (was not previously seen)."""

    @abstractmethod
    def job_exists(self, job_id: str) -> bool: ...

    @abstractmethod
    def record_run(self, report: RunReport) -> int: ...

    @abstractmethod
    def record_matches(self, run_id: int, matches: list[MatchResult]) -> None: ...

    @abstractmethod
    def save_cv(self, path: str, text: str, embedding: bytes | None, model: str) -> None: ...

    @abstractmethod
    def get_cv(self) -> dict | None: ...

    @abstractmethod
    def get_jobs(self) -> list["Job"]: ...

    @abstractmethod
    def set_job_embedding(self, job_id: str, embedding: bytes) -> None: ...

    @abstractmethod
    def get_job_embedding(self, job_id: str) -> bytes | None: ...

    @abstractmethod
    def get_notified_job_ids(self) -> set[str]: ...

    @abstractmethod
    def mark_notified(self, job_ids: list[str]) -> None: ...

    @abstractmethod
    def save_preferences(self, preferences: "Preferences") -> None: ...

    @abstractmethod
    def get_preferences(self) -> "Preferences | None": ...
