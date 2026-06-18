import re

import httpx
import structlog

logger = structlog.get_logger()
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# var comeetvar = {"comeet_token":"...", ... "comeet_uid":"..."}
_WP = re.compile(r'"comeet_token"\s*:\s*"([^"]+)".*?"comeet_uid"\s*:\s*"([^"]+)"', re.DOTALL)
# COMEET.init({ "token":"...", "company-uid":"..." })
_INIT = re.compile(r'"token"\s*:\s*"([^"]+)"[^}]*?"company-uid"\s*:\s*"([^"]+)"', re.DOTALL)
# runtime request URL: careers-api/2.0/company/{uid}/positions?token={token}
_NET = re.compile(r"careers-api/[\d.]+/company/([^/?]+)/positions[^\s]*?token=([^&\s\"']+)", re.I)


def harvest_from_html(html: str) -> str | None:
    """Extract '{uid}:{token}' from a Comeet careers page's HTML, or None."""
    for rx in (_WP, _INIT):
        m = rx.search(html)
        if m:
            token, uid = m.group(1), m.group(2)
            return f"{uid}:{token}"
    m = _NET.search(html)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    return None


def harvest_comeet(careers_url: str, *, client: httpx.Client | None = None,
                   use_browser: bool = True) -> str | None:
    own = client or httpx.Client(timeout=20, headers={"User-Agent": _UA}, follow_redirects=True)
    try:
        result = harvest_from_html(own.get(careers_url).text)
        if result:
            return result
    except Exception as error:
        logger.warning("comeet_html_fetch_failed", url=careers_url, error=str(error))
    finally:
        if client is None:
            own.close()
    if use_browser:
        return _harvest_with_browser(careers_url)
    return None


def _harvest_with_browser(careers_url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright_unavailable_for_comeet_fallback")
        return None
    found: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            def on_request(req):
                m = _NET.search(req.url)
                if m:
                    found.append(f"{m.group(1)}:{m.group(2)}")

            page.on("request", on_request)
            page.goto(careers_url, timeout=30000, wait_until="networkidle")
            browser.close()
    except Exception as error:
        logger.warning("comeet_browser_harvest_failed", url=careers_url, error=str(error))
    return found[0] if found else None
