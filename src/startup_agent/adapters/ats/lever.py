import structlog

from startup_agent.adapters.ats._dates import parse_ms
from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.ports.ats import ATSAdapter

logger = structlog.get_logger()

_BASE = "https://api.lever.co/v0/postings/{token}?mode=json"


class LeverAdapter(ATSAdapter):
    ats_type = AtsType.LEVER

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload:  # Lever returns a top-level list
            try:
                categories = raw.get("categories") or {}
                jobs.append(Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["id"]),
                    title=raw["text"],
                    url=raw.get("hostedUrl") or raw.get("applyUrl"),
                    location=categories.get("location"),
                    description=raw.get("descriptionPlain"),
                    posted_at=parse_ms(raw.get("createdAt")),
                ))
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name, ats=self.ats_type.value, error=str(error))
                continue
        return jobs
