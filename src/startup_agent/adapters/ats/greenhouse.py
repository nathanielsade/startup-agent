import html
from datetime import datetime

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job

_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class GreenhouseAdapter:
    ats_type = AtsType.GREENHOUSE

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("jobs", []):
            location = (raw.get("location") or {}).get("name")
            content = raw.get("content")
            jobs.append(
                Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["id"]),
                    title=raw["title"],
                    url=raw["absolute_url"],
                    location=location,
                    description=html.unescape(content) if content else None,
                    posted_at=_parse_dt(raw.get("first_published") or raw.get("updated_at")),
                )
            )
        return jobs
