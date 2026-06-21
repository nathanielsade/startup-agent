from startup_agent.domain.models import Company, Job, MatchResult, RunReport
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.repository import JobRepository
from startup_agent.ports.user_repository import UserRepository


class UserScopedRepository(JobRepository):
    """A per-user view over the shared job store.

    Shared data (companies, jobs, embeddings, runs) delegates to the shared
    `JobRepository`; the single-tenant `cv`/`preferences` methods are redirected to
    the per-user `UserRepository` for `user_id`. This lets the existing matching
    services (which call `repo.get_cv()` / `repo.get_preferences()`) run per-user
    with no changes.
    """

    def __init__(self, jobs: JobRepository, users: UserRepository, user_id: str) -> None:
        self._jobs = jobs
        self._users = users
        self._uid = user_id

    # ── shared → delegate ────────────────────────────────────────────────
    def upsert_company(self, company: Company) -> str:
        return self._jobs.upsert_company(company)

    def get_companies(self, active_only: bool = True) -> list[Company]:
        return self._jobs.get_companies(active_only)

    def upsert_job(self, job: Job) -> bool:
        return self._jobs.upsert_job(job)

    def job_exists(self, job_id: str) -> bool:
        return self._jobs.job_exists(job_id)

    def get_jobs(self) -> list[Job]:
        return self._jobs.get_jobs()

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get_job(job_id)

    def set_job_embedding(self, job_id: str, embedding: bytes) -> None:
        self._jobs.set_job_embedding(job_id, embedding)

    def get_job_embedding(self, job_id: str) -> bytes | None:
        return self._jobs.get_job_embedding(job_id)

    def get_notified_job_ids(self) -> set[str]:
        return self._jobs.get_notified_job_ids()

    def mark_notified(self, job_ids: list[str]) -> None:
        self._jobs.mark_notified(job_ids)

    def record_run(self, report: RunReport) -> int:
        return self._jobs.record_run(report)

    def record_matches(self, run_id: int, matches: list[MatchResult]) -> None:
        self._jobs.record_matches(run_id, matches)

    # ── single-tenant in the port → per-user under the hood ──────────────
    def save_cv(self, path: str, text: str, embedding: bytes | None, model: str) -> None:
        self._users.save_cv(self._uid, text, embedding, model)

    def get_cv(self) -> dict | None:
        return self._users.get_cv(self._uid)

    def save_preferences(self, preferences: Preferences) -> None:
        self._users.save_preferences(self._uid, preferences)

    def get_preferences(self) -> Preferences | None:
        return self._users.get_preferences(self._uid)

    # applicant profile (not on the JobRepository ABC; routes call these directly,
    # available on both SQLiteJobRepository and here)
    def save_profile(self, profile) -> None:
        self._users.save_applicant_profile(self._uid, profile)

    def get_profile(self):
        return self._users.get_applicant_profile(self._uid)
