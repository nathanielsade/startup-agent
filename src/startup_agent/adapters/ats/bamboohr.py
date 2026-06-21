import structlog

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.ports.ats import ATSAdapter

logger = structlog.get_logger()

_BASE = "https://{token}.bamboohr.com/careers/list"


class BambooHrAdapter(ATSAdapter):
    ats_type = AtsType.BAMBOOHR

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("result", []):
            try:
                loc = raw.get("location") or {}
                parts = [loc.get("city"), loc.get("state")]
                location = ", ".join(p for p in parts if p)
                if not location and raw.get("isRemote"):
                    location = "Remote"
                jid = str(raw["id"])
                jobs.append(
                    Job(
                        company_id=company.id_hash,
                        ats_job_id=jid,
                        title=raw["jobOpeningName"],
                        url=f"https://{company.ats_token}.bamboohr.com/careers/{jid}",
                        location=location or None,
                        description=None,
                        posted_at=None,
                    )
                )
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name,
                               ats=self.ats_type.value, error=str(error))
        return jobs
