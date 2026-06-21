import html as _html
import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import structlog

from startup_agent.adapters.ats._dates import parse_dt
from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.ports.ats import ATSAdapter

logger = structlog.get_logger()

_BASE = "https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}"
_MAX_WORKERS = 8
_PAGE_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_DESC_RE = re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"')
# Comeet's full content lives in a "details" array of {order, name, value} sections
# (Description / Responsibilities / Requirements / …). The top-level "description"
# field is only the intro, so requirements (e.g. "5+ years") were being missed.
_DETAIL_RE = re.compile(
    r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"value"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _unescape_json_str(raw: str) -> str | None:
    try:
        return json.loads('"' + raw + '"')
    except (ValueError, json.JSONDecodeError):
        return None


def extract_description(page_html: str) -> str | None:
    """Plain-text job description from a Comeet hosted page.

    Prefers the full "details" sections (Description/Responsibilities/Requirements);
    falls back to the intro-only "description" field when no details are present.
    """
    if not page_html:
        return None
    sections: list[str] = []
    for name, value in _DETAIL_RE.findall(page_html):
        n, v = _unescape_json_str(name), _unescape_json_str(value)
        if n is not None and v is not None:
            sections.append(f"{n}: {v}")
    raw = " ".join(sections)
    if not raw:  # no details on the page → fall back to the intro description field
        match = _DESC_RE.search(page_html)
        if not match:
            return None
        raw = _unescape_json_str(match.group(1))
        if raw is None:
            return None
    text = _WS_RE.sub(" ", _html.unescape(_TAG_RE.sub(" ", raw))).strip()
    return text or None


def _default_fetch_page(url: str) -> str:
    resp = httpx.get(url, timeout=10.0, follow_redirects=True, headers={"User-Agent": _PAGE_UA})
    resp.raise_for_status()
    return resp.text


class ComeetAdapter(ATSAdapter):
    ats_type = AtsType.COMEET

    def __init__(self, fetch_json: JsonFetcher | None = None,
                 fetch_page: Callable[[str], str] | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()
        self._fetch_page = fetch_page or _default_fetch_page

    def fetch_jobs(self, company: Company) -> list[Job]:
        token_field = company.ats_token or ""
        if ":" not in token_field:
            logger.warning("comeet_missing_uid_token", company=company.name)
            return []
        uid, token = token_field.split(":", 1)
        payload = self._fetch(_BASE.format(uid=uid, token=token))
        jobs: list[Job] = []
        job_pages: list[tuple[Job, str]] = []
        for raw in payload:  # Comeet returns a top-level list
            try:
                location = raw.get("location") or {}
                job = Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["uid"]),
                    title=raw["name"],
                    url=(raw.get("url_active_page") or raw.get("position_url")
                         or raw.get("url_comeet_hosted_page")),
                    location=location.get("name"),
                    description=None,
                    posted_at=parse_dt(raw.get("time_updated")),
                )
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name, ats="comeet", error=str(error))
                continue
            jobs.append(job)
            hosted = raw.get("url_comeet_hosted_page") or raw.get("position_url")
            if hosted:
                job_pages.append((job, hosted))

        self._enrich_descriptions(company, job_pages)
        return jobs

    def _enrich_descriptions(self, company: Company,
                             job_pages: list[tuple[Job, str]]) -> None:
        if not job_pages:
            return
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(self._fetch_page, url): job for job, url in job_pages}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    desc = extract_description(future.result())
                except Exception as error:
                    logger.warning("comeet_description_failed", company=company.name,
                                   job=job.title, error=str(error))
                    continue
                if desc:
                    job.description = desc
