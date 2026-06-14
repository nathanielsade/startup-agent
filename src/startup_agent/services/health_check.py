import structlog

from startup_agent.domain.models import CompanyHealth
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()


class CompanyHealthChecker:
    def __init__(self, repo: JobRepository, factory: ATSAdapterFactory) -> None:
        self._repo = repo
        self._factory = factory

    def check(self) -> list[CompanyHealth]:
        results: list[CompanyHealth] = []
        for company in self._repo.get_companies():
            adapter = self._factory.for_company(company)
            if adapter is None:
                results.append(CompanyHealth(name=company.name,
                                             ats_type=company.ats_type.value,
                                             status="unsupported"))
                continue
            try:
                jobs = adapter.fetch_jobs(company)
                results.append(CompanyHealth(
                    name=company.name, ats_type=company.ats_type.value,
                    status="ok" if jobs else "empty", job_count=len(jobs)))
            except Exception as error:  # per-company isolation
                results.append(CompanyHealth(
                    name=company.name, ats_type=company.ats_type.value,
                    status="failed", error=str(error)[:200]))
        return results
