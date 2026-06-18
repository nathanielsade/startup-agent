"""Harvest Comeet uid:token pairs for all comeet companies in companies_recruiting_v2.json."""

import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
import structlog

from startup_agent.companies.comeet_harvester import harvest_comeet

logger = structlog.get_logger()

_ROOT = Path(__file__).parent.parent
_SOURCE = _ROOT / "spike" / "fixtures" / "companies_recruiting_v2.json"
_DEST = _ROOT / "spike" / "fixtures" / "comeet_tokens.json"

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _domain(website: str) -> str:
    """Return hostname without www. prefix."""
    host = urlparse(website).hostname or ""
    return host.removeprefix("www.")


def _candidate_urls(name: str, website: str) -> list[str]:
    domain = _domain(website)
    slug = name.lower().replace(" ", "-")
    return [
        f"https://{domain}/careers",
        f"https://{domain}/careers/",
        f"https://{domain}/jobs",
        f"https://careers.{domain}",
        f"https://www.comeet.com/jobs/{slug}",
    ]


def main() -> None:
    companies = [
        c for c in json.loads(_SOURCE.read_text()) if c.get("ats_type") == "comeet"
    ]
    print(f"Found {len(companies)} comeet companies")

    results: list[dict] = []
    html_ok = 0
    browser_ok = 0
    failed = 0

    with httpx.Client(
        timeout=15, headers={"User-Agent": _UA}, follow_redirects=True
    ) as client:
        for idx, company in enumerate(companies, 1):
            name = company.get("name") or ""
            website = company.get("website") or ""
            print(f"[{idx}/{len(companies)}] {name} ({website})")

            if not website:
                print("  -> SKIP (no website)")
                failed += 1
                continue

            candidates = _candidate_urls(name, website)
            token: str | None = None
            via_browser = False

            # Phase 1: HTML-only across all 5 candidate URLs
            for url in candidates:
                try:
                    token = harvest_comeet(url, client=client, use_browser=False)
                except Exception as exc:
                    logger.warning("harvest_url_exception", url=url, error=str(exc))
                    token = None
                if token:
                    print(f"  -> OK (html) via {url}: {token}")
                    html_ok += 1
                    break

            # Phase 2: Browser fallback on /careers only (first candidate)
            if not token:
                fallback_url = candidates[0]  # https://{domain}/careers
                try:
                    token = harvest_comeet(fallback_url, client=client, use_browser=True)
                except Exception as exc:
                    logger.warning("harvest_browser_exception", url=fallback_url, error=str(exc))
                    token = None
                if token:
                    print(f"  -> OK (browser) via {fallback_url}: {token}")
                    via_browser = True
                    browser_ok += 1

            # Reject template placeholders like ${TOKEN}
            if token and "${" in token:
                logger.warning("comeet_token_is_placeholder", name=name, token=token)
                token = None

            if token:
                results.append(
                    {
                        "name": name,
                        "website": website,
                        "ats_type": "comeet",
                        "ats_token": token,
                    }
                )
            else:
                print("  -> FAILED")
                failed += 1

    _DEST.write_text(json.dumps(results, indent=2) + "\n")

    total_ok = html_ok + browser_ok
    print(
        f"\nSummary: attempted={len(companies)}, "
        f"succeeded={total_ok} (html={html_ok}, browser={browser_ok}), "
        f"failed={failed}"
    )
    print(f"Written {len(results)} entries to {_DEST}")


if __name__ == "__main__":
    main()
