import structlog

from startup_agent.domain.models import RunReport
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()


class IngestionService:
    def __init__(self, repo: JobRepository, factory: ATSAdapterFactory,
                 job_filter=None) -> None:
        self._repo = repo
        self._factory = factory
        self._job_filter = job_filter  # optional Callable[[Job], bool]; None = keep all

    def run(self, progress=None) -> RunReport:
        companies = self._repo.get_companies()
        total = len(companies)
        report = RunReport(companies_count=total)
        had_failure = False

        for index, company in enumerate(companies, start=1):
            adapter = self._factory.for_company(company)
            if adapter is None:
                logger.info("skip_unsupported_ats", company=company.name,
                            ats_type=company.ats_type.value)
            else:
                try:
                    jobs = adapter.fetch_jobs(company)
                    report.jobs_fetched += len(jobs)
                    for job in jobs:
                        if self._job_filter is not None and not self._job_filter(job):
                            continue  # e.g. drop non-Israel jobs at the source
                        if self._repo.upsert_job(job):
                            report.jobs_new += 1
                except Exception as error:  # per-company isolation
                    had_failure = True
                    logger.warning("fetch_failed", company=company.name, error=str(error))

            if progress is not None:
                progress({
                    "done": index, "total": total, "company": company.name,
                    "jobs_fetched": report.jobs_fetched, "jobs_new": report.jobs_new,
                })

        report.status = "partial" if had_failure else "success"
        self._repo.record_run(report)
        return report
