from datetime import datetime

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class AshbyAdapter:
    ats_type = AtsType.ASHBY

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("jobs", []):
            jobs.append(
                Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["id"]),
                    title=raw["title"],
                    url=raw.get("jobUrl") or raw.get("applyUrl"),
                    location=raw.get("location"),
                    description=raw.get("descriptionPlain"),
                    posted_at=_parse_dt(raw.get("publishedAt")),
                )
            )
        return jobs
