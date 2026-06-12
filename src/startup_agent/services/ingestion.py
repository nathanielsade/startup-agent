import structlog

from startup_agent.domain.models import RunReport
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()


class IngestionService:
    def __init__(self, repo: JobRepository, factory: ATSAdapterFactory) -> None:
        self._repo = repo
        self._factory = factory

    def run(self) -> RunReport:
        companies = self._repo.get_companies()
        report = RunReport(companies_count=len(companies))
        had_failure = False

        for company in companies:
            adapter = self._factory.for_company(company)
            if adapter is None:
                logger.info("skip_unsupported_ats", company=company.name,
                            ats_type=company.ats_type.value)
                continue
            try:
                jobs = adapter.fetch_jobs(company)
            except Exception as error:  # per-company isolation
                had_failure = True
                logger.warning("fetch_failed", company=company.name, error=str(error))
                continue
            report.jobs_fetched += len(jobs)
            for job in jobs:
                if self._repo.upsert_job(job):
                    report.jobs_new += 1

        report.status = "partial" if had_failure else "success"
        self._repo.record_run(report)
        return report
