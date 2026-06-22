"""
build_seed.py — Build a deduplicated Israeli startup seed list.

Sources:
1. GitHub: KaplanOpenSource/israeli-opensource-companies README.md
2. Failory: https://www.failory.com/startups/israel
3. Curated: spike/fixtures/snc_sample.json

Output:
- spike/fixtures/companies_seed.json
- spike/dedup_stats.md
"""

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse

# ── paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
FIXTURE_DIR = Path(__file__).parent / "fixtures"
OUT_JSON = FIXTURE_DIR / "companies_seed.json"
OUT_STATS = Path(__file__).parent / "dedup_stats.md"
SNC_JSON = FIXTURE_DIR / "snc_sample.json"

# ── helpers ──────────────────────────────────────────────────────────────────
_LEGAL_SUFFIXES = re.compile(
    r"\s+(ltd\.?|llc\.?|inc\.?|corp\.?|co\.?|s\.?a\.?|gmbh|bv|nv|plc|limited|incorporated)$",
    re.IGNORECASE,
)

def normalise_domain(url: str) -> str | None:
    """Return registrable domain (e.g. wiz.io) or None if unparseable."""
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        host = urlparse(url).netloc or urlparse(url).path
        host = host.lower().strip("/")
        # strip port
        host = host.split(":")[0]
        # strip www.
        if host.startswith("www."):
            host = host[4:]
        if not host or "." not in host:
            return None
        return host
    except Exception:
        return None


def normalise_name(name: str) -> str:
    """Lowercase, strip legal suffixes, collapse whitespace, strip punctuation."""
    s = name.lower().strip()
    s = _LEGAL_SUFFIXES.sub("", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def make_key(name: str, website: str) -> str:
    domain = normalise_domain(website)
    if domain:
        return domain
    return normalise_name(name)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


# ── source 1: GitHub ─────────────────────────────────────────────────────────
def fetch_github() -> list[dict]:
    for branch in ("main", "master"):
        url = (
            f"https://raw.githubusercontent.com/KaplanOpenSource/"
            f"israeli-opensource-companies/{branch}/README.md"
        )
        try:
            text = fetch(url)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
    else:
        print("  [github] README not found on main or master")
        return []

    companies = []
    # Parse markdown tables: | Name | Website | ... |
    # We look for rows that have a pipe-separated structure with links
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        # Skip header/separator rows
        if re.match(r"^[-:]+$", cells[0]):
            continue
        if cells[0].lower() in ("name", "company", "organization", ""):
            continue

        name_cell = cells[0]
        # Extract name from [Name](url) or plain text
        link_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", name_cell)
        if link_match:
            name = link_match.group(1).strip()
            website = link_match.group(2).strip()
        else:
            name = re.sub(r"[*_`]", "", name_cell).strip()
            # Try to find URL in any cell
            website = ""
            for cell in cells[1:]:
                m = re.search(r"https?://[^\s)\]]+", cell)
                if m:
                    website = m.group(0)
                    break
                m2 = re.search(r"\[([^\]]+)\]\(([^)]+)\)", cell)
                if m2:
                    website = m2.group(2)
                    break

        if not name or name.startswith("---"):
            continue
        companies.append({"name": name, "website": website, "sources": ["github"]})

    print(f"  [github] parsed {len(companies)} rows")
    return companies


# ── source 2: Failory ────────────────────────────────────────────────────────
def fetch_failory() -> list[dict]:
    url = "https://www.failory.com/startups/israel"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  [failory] fetch failed: {e}")
        return []

    companies = []

    # Strategy 1: look for JSON-LD or structured data
    # Strategy 2: look for card-like patterns with company names + links
    # Pattern: anchor tags with company names and optional hrefs pointing out
    # Failory typically has <a href="https://company.com">Company Name</a>
    # or <h3>Company Name</h3> near <a href="...">

    # Extract all external links with anchor text (non-failory domains)
    ext_links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{2,80})\s*</a>',
        html,
        re.IGNORECASE,
    )

    seen_names: set[str] = set()
    for href, text in ext_links:
        text = text.strip()
        href = href.strip()
        # skip navigation, social, failory-internal
        if not text or len(text) < 2:
            continue
        if any(
            s in href.lower()
            for s in ["failory.com", "twitter.com", "linkedin.com", "facebook.com",
                       "crunchbase.com", "producthunt.com", "javascript:", "#", "mailto:"]
        ):
            continue
        if href.startswith("/") or not href.startswith("http"):
            continue
        # skip generic nav text
        if text.lower() in (
            "read more", "learn more", "visit", "website", "visit website",
            "see more", "here", "check out", "startup", "israel", "startups",
        ):
            continue

        domain = normalise_domain(href)
        if not domain:
            continue

        key = normalise_name(text)
        if key in seen_names:
            continue
        seen_names.add(key)
        companies.append({"name": text, "website": href, "sources": ["failory"]})

    # Strategy 3: grab h3/h2/strong company-name patterns if we got few results
    if len(companies) < 10:
        headings = re.findall(
            r"<h[23][^>]*>\s*<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>([^<]{2,80})</a>",
            html,
            re.IGNORECASE,
        )
        for href, name in headings:
            name = name.strip()
            if normalise_name(name) not in seen_names:
                seen_names.add(normalise_name(name))
                companies.append({"name": name, "website": href, "sources": ["failory"]})

    print(f"  [failory] parsed {len(companies)} entries")
    return companies


# ── source 3: curated snc_sample.json ────────────────────────────────────────
def load_curated() -> list[dict]:
    with open(SNC_JSON) as f:
        data = json.load(f)
    companies = []
    for c in data.get("companies", []):
        name = c.get("name", "").strip()
        if not name:
            continue
        # snc_sample has no website field; try to derive from ats_token or name
        website = c.get("website", "")
        if not website:
            # best-effort: use name as lower-case domain guess (will fall back to name key)
            pass
        companies.append({"name": name, "website": website, "sources": ["curated"]})
    print(f"  [curated] loaded {len(companies)} entries")
    return companies


# ── dedup ────────────────────────────────────────────────────────────────────
def dedup(all_companies: list[dict]) -> list[dict]:
    # Pass 1: build a normalised-name → domain map from entries that have websites
    name_to_domain: dict[str, str] = {}
    for c in all_companies:
        domain = normalise_domain(c.get("website", ""))
        if domain:
            name_to_domain[normalise_name(c["name"])] = domain

    merged: dict[str, dict] = {}
    for c in all_companies:
        website = c.get("website", "")
        domain = normalise_domain(website)

        # For no-website entries, try to resolve domain via the name map
        if not domain:
            domain = name_to_domain.get(normalise_name(c["name"]))

        key = domain if domain else normalise_name(c["name"])

        if key not in merged:
            merged[key] = {
                "name": c["name"],
                "website": domain or "",
                "sources": list(c["sources"]),
            }
        else:
            existing = merged[key]
            # fill missing website
            if not existing["website"] and domain:
                existing["website"] = domain
            # prefer the richer/shorter name (heuristic: shorter usually less generic)
            if not existing["website"] and len(c["name"]) < len(existing["name"]):
                existing["name"] = c["name"]
            # merge sources
            for s in c["sources"]:
                if s not in existing["sources"]:
                    existing["sources"].append(s)
    return sorted(merged.values(), key=lambda x: x["name"].lower())


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Fetching sources...")
    github = fetch_github()
    failory = fetch_failory()
    curated = load_curated()

    raw_counts = {
        "github": len(github),
        "failory": len(failory),
        "curated": len(curated),
    }
    all_companies = github + failory + curated
    total_before = len(all_companies)

    print("Deduplicating...")
    result = dedup(all_companies)
    total_after = len(result)
    dupes_removed = total_before - total_after
    with_website = sum(1 for c in result if c["website"])

    # Write JSON fixture
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Written: {OUT_JSON} ({total_after} companies)")

    # Write stats
    multi_source = [c for c in result if len(c["sources"]) > 1]
    examples = result[:5]

    stats_lines = [
        "# companies_seed.json — Dedup Stats",
        "",
        "## Source counts (raw)",
        "| Source  | Raw count |",
        "|---------|-----------|",
        f"| github  | {raw_counts['github']} |",
        f"| failory | {raw_counts['failory']} |",
        f"| curated | {raw_counts['curated']} |",
        "",
        "## Dedup summary",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total before dedup | {total_before} |",
        f"| Total after dedup  | {total_after} |",
        f"| Dupes removed      | {dupes_removed} |",
        f"| % deduped          | {dupes_removed/total_before*100:.1f}% |",
        f"| With usable website | {with_website} ({with_website/total_after*100:.1f}%) |",
        f"| Appearing in 2+ sources | {len(multi_source)} |",
        "",
        "## 5 example entries",
        "```json",
        json.dumps(examples, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Notes",
        "- GitHub source: KaplanOpenSource/israeli-opensource-companies README.md",
        "- Failory source: https://www.failory.com/startups/israel (HTML parsed via regex)",
        "- Curated source: spike/fixtures/snc_sample.json (52 manually curated startups)",
        "- Dedup key: registrable domain when available, else normalised name",
        "- First occurrence wins; missing fields filled from later sources",
    ]

    with open(OUT_STATS, "w") as f:
        f.write("\n".join(stats_lines) + "\n")
    print(f"Written: {OUT_STATS}")

    # Print summary
    print()
    print("=== STATS ===")
    for src, cnt in raw_counts.items():
        print(f"  {src}: {cnt}")
    print(f"  total before dedup: {total_before}")
    print(f"  total after dedup:  {total_after}")
    print(f"  dupes removed:      {dupes_removed}")
    print(f"  with website:       {with_website} ({with_website/total_after*100:.1f}%)")


if __name__ == "__main__":
    main()
