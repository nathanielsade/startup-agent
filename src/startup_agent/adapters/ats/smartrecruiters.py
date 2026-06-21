import structlog

from startup_agent.adapters.ats._dates import parse_dt
from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.ports.ats import ATSAdapter

logger = structlog.get_logger()

_BASE = "https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100"


class SmartRecruitersAdapter(ATSAdapter):
    ats_type = AtsType.SMARTRECRUITERS

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("content", []):
            try:
                loc = raw.get("location") or {}
                jobs.append(
                    Job(
                        company_id=company.id_hash,
                        ats_job_id=str(raw["id"]),
                        title=raw["name"],
                        url=f"https://jobs.smartrecruiters.com/{company.ats_token}/{raw['id']}",
                        location=loc.get("fullLocation") or loc.get("city"),
                        description=None,
                        posted_at=parse_dt(raw.get("releasedDate")),
                    )
                )
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name,
                               ats=self.ats_type.value, error=str(error))
        return jobs
