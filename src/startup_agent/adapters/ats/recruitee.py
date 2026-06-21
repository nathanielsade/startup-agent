import structlog

from startup_agent.adapters.ats._dates import parse_dt
from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.ports.ats import ATSAdapter

logger = structlog.get_logger()

_BASE = "https://{token}.recruitee.com/api/offers/"


class RecruiteeAdapter(ATSAdapter):
    ats_type = AtsType.RECRUITEE

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("offers", []):
            try:
                url = raw.get("careers_url") or raw.get("careers_apply_url")
                if not url:
                    continue
                jobs.append(
                    Job(
                        company_id=company.id_hash,
                        ats_job_id=str(raw.get("id") or raw.get("slug")),
                        title=raw["title"],
                        url=url,
                        location=raw.get("location") or raw.get("city"),
                        description=raw.get("description"),
                        posted_at=parse_dt(raw.get("published_at") or raw.get("created_at")
                                           or raw.get("updated_at")),
                    )
                )
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name,
                               ats=self.ats_type.value, error=str(error))
        return jobs
