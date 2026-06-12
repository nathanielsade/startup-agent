"""
Phase 0 discovery spike — Startup Nation Central (SNC) access probe.

Tries to fetch company data from finder.startupnationcentral.org.
Documents what's accessible and what's gated.
"""

import json
import time
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finder.startupnationcentral.org/",
    "Origin": "https://finder.startupnationcentral.org",
}


def probe_snc(client: httpx.Client) -> dict:
    base = "https://finder.startupnationcentral.org"
    results = {}

    # Probe 1: Main page
    print("Probing SNC main page...")
    try:
        r = client.get(base, timeout=15)
        results["main_page"] = {"status": r.status_code, "content_type": r.headers.get("content-type", "")}
        print(f"  Main: {r.status_code}")
    except Exception as e:
        results["main_page"] = {"error": str(e)}
        print(f"  Main: ERROR {e}")

    time.sleep(0.5)

    # Probe 2: Known API paths
    api_paths = [
        "/api/companies",
        "/api/v1/companies",
        "/api/v2/companies",
        "/api/startups",
        "/api/v1/startups",
        "/startups/search",
        "/api/startups/search",
        "/api/v1/startups/search",
        "/api/search",
        "/api/companies/search",
        "/graphql",
        "/api/graphql",
    ]

    print("\nProbing API endpoints...")
    for path in api_paths:
        url = base + path
        try:
            r = client.get(url, timeout=10)
            ct = r.headers.get("content-type", "")
            is_json = "json" in ct or r.text.strip().startswith(("{", "["))
            results[path] = {
                "status": r.status_code,
                "content_type": ct,
                "is_json": is_json,
                "body_prefix": r.text[:200] if r.status_code not in (404,) else None,
            }
            status_str = f"{r.status_code} {'JSON' if is_json else ''}"
            print(f"  {path}: {status_str}")
            if is_json and r.status_code == 200:
                try:
                    data = r.json()
                    print(f"    -> Keys: {list(data.keys()) if isinstance(data, dict) else 'array len=' + str(len(data))}")
                except Exception:
                    pass
        except Exception as e:
            results[path] = {"error": str(e)}
            print(f"  {path}: ERROR {e}")
        time.sleep(0.3)

    # Probe 3: POST to search endpoint
    print("\nProbing POST search endpoints...")
    search_payloads = [
        ("/startups/search", {"page": 1, "limit": 20, "filters": {}}),
        ("/api/v1/startups/search", {"page": 1, "size": 20}),
        ("/api/companies/search", {"query": "", "page": 1}),
    ]

    for path, payload in search_payloads:
        url = base + path
        try:
            r = client.post(
                url,
                json=payload,
                headers={**HEADERS, "Content-Type": "application/json"},
                timeout=10,
            )
            ct = r.headers.get("content-type", "")
            is_json = "json" in ct
            results[f"POST:{path}"] = {
                "status": r.status_code,
                "content_type": ct,
                "is_json": is_json,
                "body_prefix": r.text[:300],
            }
            print(f"  POST {path}: {r.status_code} {'JSON' if is_json else ''}")
            if r.status_code == 200 and is_json:
                try:
                    data = r.json()
                    print(f"    -> Keys/len: {list(data.keys()) if isinstance(data, dict) else len(data)}")
                except Exception:
                    pass
        except Exception as e:
            results[f"POST:{path}"] = {"error": str(e)}
            print(f"  POST {path}: ERROR {e}")
        time.sleep(0.3)

    # Probe 4: Check for authentication hints
    print("\nChecking auth hints from main page...")
    try:
        r = client.get(base, timeout=15)
        text = r.text
        import re
        # Look for API base URLs
        api_urls = re.findall(r'"(https://api\.[^"]+)"', text)[:5]
        # Look for auth tokens or API keys in meta
        auth_hints = re.findall(r'(?:apiKey|api_key|authToken|auth_token|ACCESS_KEY)["\s:=]+["\']([^"\']+)["\']', text, re.I)[:3]
        print(f"  API URLs found: {api_urls}")
        print(f"  Auth hints: {auth_hints}")
        results["auth_probe"] = {"api_urls": api_urls, "auth_hints": auth_hints}
    except Exception as e:
        results["auth_probe"] = {"error": str(e)}

    return results


def try_alternative_sources(client: httpx.Client) -> dict:
    """Try alternative free company list sources."""
    print("\n=== Alternative Sources ===")
    alternatives = {}

    # 1. IVC Research Center / IVC Online - Israeli VC/startup data
    print("\nTrying IVC Online...")
    try:
        r = client.get("https://www.ivc-online.com/", timeout=10)
        alternatives["ivc_online"] = {"status": r.status_code, "accessible": r.status_code == 200}
        print(f"  IVC Online: {r.status_code}")
    except Exception as e:
        alternatives["ivc_online"] = {"error": str(e)}
        print(f"  IVC Online: ERROR {e}")

    # 2. Start-Up Nation Finder via unofficial/community API
    print("\nTrying community/scraper endpoints...")

    # 3. LinkedIn Job Search API (public, no auth) - great for Israeli companies
    # https://www.linkedin.com/jobs/search/?location=Israel
    try:
        r = client.get(
            "https://www.linkedin.com/jobs/search/?keywords=&location=Israel&f_C=&start=0&count=10",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        alternatives["linkedin_jobs"] = {"status": r.status_code, "note": "Requires auth cookie"}
        print(f"  LinkedIn Jobs: {r.status_code}")
    except Exception as e:
        alternatives["linkedin_jobs"] = {"error": str(e)}

    time.sleep(0.3)

    # 4. GitHub awesome lists - known free data sources
    awesome_urls = [
        ("awesome-israel-tech", "https://raw.githubusercontent.com/yanirs/established-remote/master/README.md"),
        ("geektime_iltech", "https://raw.githubusercontent.com/geektime-geekway/companies-reviews/main/README.md"),
    ]
    for name, url in awesome_urls:
        try:
            r = client.get(url, timeout=10)
            alternatives[name] = {"status": r.status_code, "len": len(r.text) if r.status_code == 200 else 0}
            print(f"  {name}: {r.status_code} ({len(r.text)} chars)")
        except Exception as e:
            alternatives[name] = {"error": str(e)}
        time.sleep(0.3)

    return alternatives


def main() -> None:
    print("Phase 0 — SNC access probe")
    print(f"Target: https://finder.startupnationcentral.org")
    print()

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        snc_results = probe_snc(client)
        alt_results = try_alternative_sources(client)

    # Compile summary
    working_endpoints = [k for k, v in snc_results.items() if isinstance(v, dict) and v.get("status") == 200]
    print(f"\n=== Summary ===")
    print(f"Working SNC endpoints: {working_endpoints}")
    print(f"SNC accessible: {bool(working_endpoints)}")

    output = {
        "snc": snc_results,
        "alternatives": alt_results,
        "summary": {
            "snc_working_endpoints": working_endpoints,
            "snc_verdict": "accessible" if working_endpoints else "gated_or_blocked",
        },
    }

    path = FIXTURES / "snc_probe.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
