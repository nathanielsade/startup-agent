# Israeli Companies Spike Report

**Date:** 2026-06-18  
**Output file:** `spike/fixtures/companies_recruiting_v2.json`

---

## 1. New Total Unique Companies

| Version | Count | Change |
|---------|-------|--------|
| v1 (israelvcforum only) | 909 | — |
| v2 (multi-board + dedup) | **930** | +21 net new |

The 21 net-new companies came from NFX, Insight Partners, and TLV Partners boards after deduplication. Most companies on those boards were already in the israelvcforum dataset.

---

## 2. Getro Boards Surveyed

### How Collection IDs Were Found

Getro boards are Next.js SPAs. The collection/network ID is embedded in `__NEXT_DATA__` as `props.pageProps.network.id`. Companies are scraped from `/companies?page=N` which also embeds company data (including domain) in `initialState.companies.found`.

### Boards That Worked

| VC Board | URL | Network ID | Companies |
|----------|-----|------------|-----------|
| Israeli VC Forum | israelvcforum.getro.com | 10949 | 888 (already in v1) |
| NFX | jobs.nfx.com | 307 | 156 scraped → **6 net new** |
| Insight Partners | jobs.insightpartners.com | 246 | 528 scraped → **11 net new** |
| TLV Partners | jobs.tlv.partners | 190 | 36 scraped → **4 net new** |
| Aleph | aleph.getro.com | 21393 | 0 (board exists, API returns empty) |
| Grove Ventures | grove.getro.com | 16076 | 0 (board exists, API returns empty) |

### Boards Not Found (no Getro board)

The following VCs do **not** have discoverable Getro-powered job boards:

Vintage Investment Partners, Team8, Pitango, Glilot Capital, Entrée Capital, F2 Venture Capital, StageOne Ventures, Viola Ventures, JVP, Hetz Ventures, Bessemer Venture Partners, Vertex Israel, Lightspeed.

These VCs either use custom job boards, LinkedIn, or other systems — not Getro.

### Why Low Net-New Numbers

The israelvcforum board is comprehensive — it already lists portfolio companies from many of the same VCs. NFX (US-focused VC, 150 portfolio cos), Insight Partners (523 portfolio cos), and TLV Partners (36 companies) largely overlap with the israelvcforum dataset.

---

## 3. ATS Breakdown in v2

### Full Breakdown

| ATS Type | Count | % |
|----------|-------|---|
| unknown | 580 | 62.4% |
| greenhouse | 127 | 13.7% |
| comeet | 84 | 9.0% |
| ashby | 59 | 6.3% |
| lever | 39 | 4.2% |
| workday | 15 | 1.6% |
| workable | 8 | 0.9% |
| teamtailor | 7 | 0.8% |
| bamboohr | 6 | 0.6% |
| recruitee | 2 | 0.2% |
| rippling | 2 | 0.2% |
| smartrecruiters | 1 | 0.1% |
| **TOTAL** | **930** | |

### Newly Detected in v2 (from 21 new companies)

6 companies got ATS detected:
- 6sense → greenhouse (`6sense`)
- A Place for Mom → ashby (`a-place-for-mom`)
- acceldata → lever (`acceldata`)
- Afresh Technologies → greenhouse (`afresh`)
- Unframe → greenhouse (`unframe`)
- REAL → ashby (`real`)

### Reachable with Supported APIs

| Category | Count |
|----------|-------|
| Greenhouse + Ashby + Lever reachable | **225** |
| Comeet reachable (with token — see Task C) | **84** |
| Unknown/other ATS | 621 |

---

## 4. Comeet API — Definitive Verdict

### Verdict: YES — Public JSON API accessible without a headless browser, but requires a per-company token

### Evidence

**Endpoint pattern:**
```
GET https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}
```

Both `comeet.co` and `comeet.com` work. No special `Accept` header required.

**Tested working examples:**

| Company | UID | Token | Result |
|---------|-----|-------|--------|
| Global-e | `62.002` | `262988131015727264C41572E4C10AE10AE` | ✓ 200, 78 positions |
| Aqua Security | `91.001` | `191644966966644E194B3191644644` | ✓ 200, 12 positions |

**Why it initially looked broken:**  
Without a token → `HTTP 400, {"status":400,"message":"Token is missing"}`.  
Without correct Accept header (some versions) → `HTTP 406`.  
With the correct token → `HTTP 200, application/json`.

**Token extraction method:**  
The token and UID are embedded in the company's own careers page via a `COMEET.init({...})` JavaScript call:
```html
<script>
   window.comeetInit = function() {
      COMEET.init({
         "token":       "262988131015727264C41572E4C10AE10AE",
         "company-uid": "62.002",
         "company-name":"Global-e",
         ...
      });
   }
</script>
```

Pattern to extract from HTML:
```python
m = re.search(r'COMEET\.init\s*\(\s*\{[^}]+\}', html)
# then extract "token" and "company-uid" keys
```

### Full Field Map (v2.0 response)

Each position object returned by the API has:

| Field | Type | Description |
|-------|------|-------------|
| `uid` | string | Unique position ID (e.g., `"8C.B66"`) |
| `name` | string | Job title |
| `department` | string | Department name |
| `location.name` | string | Human-readable location |
| `location.country` | string | ISO country code |
| `location.city` | string | City |
| `location.is_remote` | bool | Remote flag |
| `employment_type` | string | Full-time / Part-time / etc. |
| `experience_level` | string | Seniority level |
| `workplace_type` | string | "remote", "hybrid", "on-site" |
| `url_comeet_hosted_page` | string | Canonical Comeet job URL |
| `url_recruit_hosted_page` | string | Company's own job URL |
| `url_active_page` | string | Preferred apply URL |
| `time_updated` | string | ISO datetime of last update |
| `company_name` | string | Company name |
| `is_internal` | bool | Internal-only posting flag |
| `picture_url` | string | Job image URL (if any) |
| `email` | string | Apply-by-email address |

**v1.0 vs v2.0:** v1.0 uses `email_name` instead of `email`; otherwise identical. Stick with v2.0.

### Implication for the 84 Comeet companies in v2

All 84 Comeet companies are reachable **if** we can extract their UID and token from their careers page. This requires:
1. Knowing/finding their careers page URL
2. Fetching it (no JS execution needed — token is in raw HTML)
3. Extracting `COMEET.init({"company-uid": ..., "token": ...})`

Some companies embed Comeet in a WP plugin (CSS filename `comeet-{N}.css`) — same extraction method works.

---

## 5. Confirmation: /Users/netanelsade/conifers/ Not Touched

All work was done exclusively under:
- `/Users/netanelsade/projects/startup-agent/spike/` — output files
- `/tmp/` — scratch scripts

No files in `/Users/netanelsade/conifers/` were read, modified, or accessed.

---

## Appendix: Source Distribution

| Source | Companies |
|--------|-----------|
| getro_israel_vc_forum | 884 |
| manual_research (existing) | 25 |
| insight_getro (net new) | 11 |
| nfx_getro (net new) | 6 |
| tlv_partners_getro (net new) | 4 |
| **Total** | **930** |
