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
        # per-company outcome tally — distinguishes real ATS failures from
        # working-but-foreign-only and no-openings, so coverage gaps are visible.
        tally = {"ok": 0, "failed": 0, "empty": 0, "filtered_foreign": 0, "unsupported": 0}

        for index, company in enumerate(companies, start=1):
            adapter = self._factory.for_company(company)
            raw = stored = 0
            if adapter is None:
                outcome = "unsupported"
            else:
                try:
                    jobs = adapter.fetch_jobs(company)
                    raw = len(jobs)
                    report.jobs_fetched += raw
                    for job in jobs:
                        if self._job_filter is not None and not self._job_filter(job):
                            continue  # e.g. drop non-Israel jobs at the source
                        stored += 1
                        if self._repo.upsert_job(job):
                            report.jobs_new += 1
                    outcome = "ok" if stored else ("empty" if raw == 0 else "filtered_foreign")
                except Exception as error:  # per-company isolation
                    had_failure = True
                    outcome = "failed"
                    logger.warning("fetch_failed", company=company.name, error=str(error))

            tally[outcome] += 1
            logger.info("company_result", company=company.name,
                        ats=company.ats_type.value, outcome=outcome,
                        fetched=raw, stored=stored, dropped=raw - stored)

            if progress is not None:
                progress({
                    "done": index, "total": total, "company": company.name,
                    "jobs_fetched": report.jobs_fetched, "jobs_new": report.jobs_new,
                })

        report.status = "partial" if had_failure else "success"
        logger.info("ingest_summary", companies=total, jobs_fetched=report.jobs_fetched,
                    jobs_new=report.jobs_new, **tally)
        self._repo.record_run(report)
        return report
