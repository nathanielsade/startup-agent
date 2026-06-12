from abc import ABC, abstractmethod

from startup_agent.domain.models import Company, Job, MatchResult, RunReport


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
