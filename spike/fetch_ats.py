"""
Phase 0 discovery spike — ATS job fixture fetcher.

Tries known tokens for Israeli startups across 6 ATS platforms,
fetches raw JSON, saves to spike/fixtures/<ats>_<company>.json.
Truncates to first 50 jobs per company to keep files manageable.
"""

import json
import time
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; startup-agent-spike/0.1)",
    "Accept": "application/json",
}

MAX_JOBS = 50


def save(name: str, data: object) -> Path:
    path = FIXTURES / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  saved {path.name} ({path.stat().st_size // 1024}KB)")
    return path


def truncate_jobs(data: object, keys: list[str]) -> object:
    """Truncate job list to MAX_JOBS, preserving surrounding metadata."""
    if isinstance(data, list):
        return data[:MAX_JOBS]
    if isinstance(data, dict):
        for key in keys:
            if key in data and isinstance(data[key], list):
                data[key] = data[key][:MAX_JOBS]
    return data


# ---------------------------------------------------------------------------
# Greenhouse
# ---------------------------------------------------------------------------

GREENHOUSE_TOKENS = [
    "wiz",
    "monday",
    "lemonade",
    "snyk",
    "fireblocks",
    "melio",
    "atbay",
    "verbit",
    "aidoc",
    "riskified",
    "coralogix",
    "cyera",
    "gong",
    "pixellot",
    "drata",
]


def fetch_greenhouse(client: httpx.Client) -> None:
    print("\n=== Greenhouse ===")
    successes = 0
    for token in GREENHOUSE_TOKENS:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            r = client.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                jobs = data.get("jobs", [])
                print(f"  {token}: {len(jobs)} jobs (HTTP 200)")
                data = truncate_jobs(data, ["jobs"])
                save(f"greenhouse_{token}", data)
                successes += 1
            else:
                print(f"  {token}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {token}: ERROR {e}")
        time.sleep(0.3)
    print(f"  Greenhouse successes: {successes}/{len(GREENHOUSE_TOKENS)}")


# ---------------------------------------------------------------------------
# Lever
# ---------------------------------------------------------------------------

LEVER_TOKENS = [
    "wiz",
    "gong",
    "monday",
    "fireblocks",
    "island",
    "pinecone",
    "snyk",
    "melio",
    "lemonade",
    "cyera",
    "coralogix",
    "orca-security",
    "axonius",
]


def fetch_lever(client: httpx.Client) -> None:
    print("\n=== Lever ===")
    successes = 0
    for token in LEVER_TOKENS:
        url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        try:
            r = client.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                count = len(data) if isinstance(data, list) else "?"
                print(f"  {token}: {count} postings (HTTP 200)")
                data = truncate_jobs(data, [])
                save(f"lever_{token}", data)
                successes += 1
            else:
                print(f"  {token}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {token}: ERROR {e}")
        time.sleep(0.3)
    print(f"  Lever successes: {successes}/{len(LEVER_TOKENS)}")


# ---------------------------------------------------------------------------
# Ashby
# ---------------------------------------------------------------------------

ASHBY_TOKENS = [
    "wiz",
    "cyera",
    "island",
    "fireblocks",
    "pinecone",
    "snyk",
    "drata",
    "melio",
    "orca",
    "axonius",
    "noname",
    "claroty",
    "hunter",
]


def fetch_ashby(client: httpx.Client) -> None:
    print("\n=== Ashby ===")
    successes = 0
    for token in ASHBY_TOKENS:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        try:
            r = client.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                jobs = data.get("jobs", [])
                print(f"  {token}: {len(jobs)} jobs (HTTP 200)")
                data = truncate_jobs(data, ["jobs"])
                save(f"ashby_{token}", data)
                successes += 1
            else:
                print(f"  {token}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {token}: ERROR {e}")
        time.sleep(0.3)
    print(f"  Ashby successes: {successes}/{len(ASHBY_TOKENS)}")


# ---------------------------------------------------------------------------
# Workable
# ---------------------------------------------------------------------------

WORKABLE_TOKENS = [
    "wiz",
    "monday",
    "snyk",
    "lemonade",
    "melio",
    "riskified",
    "pixellot",
    "gong",
    "verbit",
    "coralogix",
    "atbay",
]


def fetch_workable(client: httpx.Client) -> None:
    print("\n=== Workable ===")
    successes = 0
    for token in WORKABLE_TOKENS:
        # Workable has two known URL patterns
        urls = [
            f"https://apply.workable.com/api/v3/accounts/{token}/jobs",
            f"https://{token}.workable.com/api/v3/jobs",
        ]
        found = False
        for url in urls:
            try:
                r = client.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    jobs = data.get("results", data.get("jobs", data if isinstance(data, list) else []))
                    count = len(jobs) if isinstance(jobs, list) else "?"
                    print(f"  {token}: {count} jobs via {url.split('/')[2]} (HTTP 200)")
                    data = truncate_jobs(data, ["results", "jobs"])
                    save(f"workable_{token}", data)
                    successes += 1
                    found = True
                    break
                else:
                    print(f"  {token} ({url.split('/')[2]}): HTTP {r.status_code}")
            except Exception as e:
                print(f"  {token}: ERROR {e}")
            time.sleep(0.2)
        if not found:
            pass
    print(f"  Workable successes: {successes}/{len(WORKABLE_TOKENS)}")


# ---------------------------------------------------------------------------
# SmartRecruiters
# ---------------------------------------------------------------------------

SMARTRECRUITERS_TOKENS = [
    "Wiz",
    "GongIO",
    "Gong",
    "Lemonade",
    "Riskified",
    "Pixellot",
    "Coralogix",
    "Fireblocks",
    "Melio",
    "AtBay",
    "Verbit",
    "Snyk",
    "Monday",
    "MondayDotCom",
]


def fetch_smartrecruiters(client: httpx.Client) -> None:
    print("\n=== SmartRecruiters ===")
    successes = 0
    for token in SMARTRECRUITERS_TOKENS:
        url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
        try:
            r = client.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                items = data.get("content", [])
                print(f"  {token}: {len(items)} postings (HTTP 200)")
                data = truncate_jobs(data, ["content"])
                save(f"smartrecruiters_{token.lower()}", data)
                successes += 1
            else:
                print(f"  {token}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {token}: ERROR {e}")
        time.sleep(0.3)
    print(f"  SmartRecruiters successes: {successes}/{len(SMARTRECRUITERS_TOKENS)}")


# ---------------------------------------------------------------------------
# Comeet
# ---------------------------------------------------------------------------

# Comeet tokens are usually a company UID found in the careers page URL.
# Format: https://www.comeet.com/jobs/<UID>/...
# Known UIDs for Israeli companies from public careers pages:
COMEET_TOKENS = [
    "00.006",   # typical comeet UID format
    "coinbase",
    "monday-com",
    "monday",
    "riskified",
    "similarweb",
    "walkme",
    "radware",
    "radcom",
    "varonis",
    "cyberark",
    "imperva",
    "perion",
    "amdocs",
]

# Also try the direct API endpoint pattern
COMEET_API_TOKENS = [
    "monday",
    "similarweb",
    "walkme",
    "riskified",
    "varonis",
    "cyberark",
    "imperva",
]


def fetch_comeet(client: httpx.Client) -> None:
    print("\n=== Comeet ===")
    successes = 0

    # Pattern 1: Check if comeet has a public positions endpoint
    # by scraping the comeet careers page structure
    test_companies = [
        ("similarweb", "similarweb"),
        ("walkme", "walkme"),
        ("monday-com", "monday"),
        ("cyberark", "cyberark"),
        ("varonis", "varonis"),
    ]

    for uid, name in test_companies:
        # Try the known comeet API endpoint format
        urls_to_try = [
            f"https://www.comeet.com/jobs/api/v0.1/{uid}/positions",
            f"https://www.comeet.co/jobs/api/v0.1/{uid}/positions",
            f"https://careers.comeet.co/{uid}/positions?format=json",
        ]
        found = False
        for url in urls_to_try:
            try:
                r = client.get(url, timeout=15)
                if r.status_code == 200:
                    ct = r.headers.get("content-type", "")
                    if "json" in ct or r.text.strip().startswith("[") or r.text.strip().startswith("{"):
                        data = r.json()
                        count = len(data) if isinstance(data, list) else len(data.get("positions", []))
                        print(f"  {name}: {count} positions via {url} (HTTP 200)")
                        save(f"comeet_{name}", data)
                        successes += 1
                        found = True
                        break
                    else:
                        print(f"  {name}: 200 but not JSON ({ct[:40]})")
                else:
                    print(f"  {name} [{url.split('/')[2]}...]: HTTP {r.status_code}")
            except Exception as e:
                print(f"  {name}: ERROR {e}")
            time.sleep(0.2)

    # Try fetching the Comeet embedded widget endpoint (used on embed pages)
    # Comeet career pages embed jobs as: https://www.comeet.co/jobs/{uid}?embedded=true
    # The underlying data is loaded via: https://api.comeet.co/positions?companyUid={uid}
    print("  Trying Comeet API endpoint...")
    for uid, name in test_companies:
        if found:
            break
        for api_url in [
            f"https://api.comeet.co/positions?companyUid={uid}",
            f"https://api.comeet.com/positions?companyUid={uid}",
        ]:
            try:
                r = client.get(api_url, timeout=15)
                if r.status_code == 200:
                    ct = r.headers.get("content-type", "")
                    if "json" in ct:
                        data = r.json()
                        print(f"  {name}: data via {api_url}")
                        save(f"comeet_{name}_api", data)
                        successes += 1
                        break
                else:
                    print(f"  comeet api {uid}: HTTP {r.status_code}")
            except Exception as e:
                print(f"  comeet api {uid}: ERROR {e}")
        time.sleep(0.3)

    if successes == 0:
        print("  Comeet: no direct API found — needs browser network inspection")
        save("comeet_BLOCKED", {"status": "blocked", "note": "No public REST API found; Comeet loads via embedded widget or requires auth. Need to inspect network calls on a real Comeet careers page."})

    print(f"  Comeet successes: {successes}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Phase 0 — ATS fixture fetcher")
    print(f"Saving to: {FIXTURES}")

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        fetch_greenhouse(client)
        fetch_lever(client)
        fetch_ashby(client)
        fetch_workable(client)
        fetch_smartrecruiters(client)
        fetch_comeet(client)

    print("\nDone. Fixtures saved to spike/fixtures/")
    print("Check for *_BLOCKED.json files for failed platforms.")


if __name__ == "__main__":
    main()
