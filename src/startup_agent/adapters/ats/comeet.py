import html as _html
import json
import re

import structlog

from startup_agent.adapters.ats._dates import parse_dt
from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.ports.ats import ATSAdapter

logger = structlog.get_logger()

_BASE = "https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}"

_DESC_RE = re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def extract_description(page_html: str) -> str | None:
    """Pull the embedded JSON "description" out of a Comeet hosted page → plain text."""
    if not page_html:
        return None
    match = _DESC_RE.search(page_html)
    if not match:
        return None
    try:
        raw = json.loads('"' + match.group(1) + '"')  # unescape the JSON string
    except (ValueError, json.JSONDecodeError):
        return None
    text = _WS_RE.sub(" ", _html.unescape(_TAG_RE.sub(" ", raw))).strip()
    return text or None


class ComeetAdapter(ATSAdapter):
    ats_type = AtsType.COMEET

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        token_field = company.ats_token or ""
        if ":" not in token_field:
            logger.warning("comeet_missing_uid_token", company=company.name)
            return []
        uid, token = token_field.split(":", 1)
        payload = self._fetch(_BASE.format(uid=uid, token=token))
        jobs: list[Job] = []
        for raw in payload:  # Comeet returns a top-level list
            try:
                location = raw.get("location") or {}
                jobs.append(Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["uid"]),
                    title=raw["name"],
                    url=(raw.get("url_active_page") or raw.get("position_url")
                         or raw.get("url_comeet_hosted_page")),
                    location=location.get("name"),
                    description=None,
                    posted_at=parse_dt(raw.get("time_updated")),
                ))
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name, ats="comeet", error=str(error))
                continue
        return jobs
