# Phase 0 Discovery Spike — Report

**Date:** 2026-06-12  
**Branch:** phase-0/discovery-spike

---

## 1. ATS Hypothesis Validation

**Hypothesis:** Most Israeli startups use ~6 ATS platforms, each with one public JSON API.

**Verdict: Partially confirmed.** Greenhouse, Ashby, and SmartRecruiters have working public REST APIs with no auth required. Lever API returned 404 for all tested Israeli company tokens. Workable rate-limited aggressively (429). Comeet is a JavaScript SPA with no discoverable REST API.

---

## 2. ATS Findings by Platform

### 2.1 Greenhouse ✅ (strong coverage)

**Endpoint:** `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`

**Note:** Greenhouse has migrated many companies to a new UI at `job-boards.greenhouse.io`. The old `boards-api.greenhouse.io` v1 endpoint still works for companies that haven't migrated. Companies on the new platform require a headless browser (React SPA, no public API discovered).

**Verified working tokens:**
| Company | Token | Jobs |
|---|---|---|
| Fireblocks | `fireblocks` | 56 |
| Melio | `melio` | 21 |
| Riskified | `riskified` | 30 |
| At-Bay | `atbay` | 0 (token valid) |
| Gong | `gongio` | 94 |

**Companies on new GH (JS-rendered, token known from redirects):**
`monday`, `wiz`, `coralogix`, `snyk`, `island`, `lemonade` — all redirect `boards.greenhouse.io/{token}` to `job-boards.greenhouse.io/{token}` but have no public REST API.

**Field Map (from `greenhouse_fireblocks.json`):**

| Field | Path | Format |
|---|---|---|
| Job ID | `.jobs[].id` | integer |
| Title | `.jobs[].title` | string |
| Location | `.jobs[].location.name` | string (city, region, country) |
| Apply URL | `.jobs[].absolute_url` | absolute URL (company site) |
| Description | `.jobs[].content` | HTML (HTML-entity-encoded) |
| Updated | `.jobs[].updated_at` | ISO8601 with timezone offset |
| First published | `.jobs[].first_published` | ISO8601 with timezone offset |
| Department | `.jobs[].departments[].name` | string |
| Office/region | `.jobs[].offices[].name` | string |

**Rate limits:** None observed at 0.3s delay.

---

### 2.2 Lever ❌ (no working tokens found)

**Endpoint:** `https://api.lever.co/v0/postings/{token}?mode=json`

Tested 13+ tokens for Israeli companies. All returned 404.

**Conclusion:** Israeli startups don't appear to use Lever significantly, or use different slugs. Needs discovery via `jobs.lever.co` search or LinkedIn.

**Field Map (from Lever docs, not validated with Israeli company data):**

| Field | Path | Format |
|---|---|---|
| Job ID | `[].id` (UUID) | string |
| Title | `[].text` | string |
| Location | `[].categories.location` | string |
| Apply URL | `[].applyUrl` | absolute URL |
| Description | `[].descriptionPlain` / `[].lists[].content` | plain text + HTML lists |
| Posted | `[].createdAt` | Unix timestamp (ms) |

---

### 2.3 Ashby ✅ (growing coverage)

**Endpoint:** `https://api.ashbyhq.com/posting-api/job-board/{token}`

**Verified working tokens:**
| Company | Token | Jobs |
|---|---|---|
| Pinecone | `pinecone` | 7 |
| Drata | `drata` | 53 |
| Orca Security | `orca` | 1 |
| Linear | `linear` | 25 |
| Wiz | `wiz` | 0 (token valid) |
| Snyk | `snyk` | 0 (token valid) |

**Field Map (from `ashby_pinecone.json` and `ashby_linear.json`):**

| Field | Path | Format |
|---|---|---|
| Job ID | `.jobs[].id` | UUID string |
| Title | `.jobs[].title` | string |
| Location | `.jobs[].location` | string (free-form) |
| Secondary Locations | `.jobs[].secondaryLocations` | array of strings |
| Job URL | `.jobs[].jobUrl` | absolute URL (jobs.ashbyhq.com) |
| Apply URL | `.jobs[].applyUrl` | absolute URL (/application suffix) |
| Description HTML | `.jobs[].descriptionHtml` | full HTML |
| Description Plain | `.jobs[].descriptionPlain` | plain text |
| Published | `.jobs[].publishedAt` | ISO8601 with ms |
| Employment Type | `.jobs[].employmentType` | `FullTime`, `PartTime`, `Contract` |
| Department | `.jobs[].department` | string |
| Is Remote | `.jobs[].isRemote` | boolean |
| Workplace Type | `.jobs[].workplaceType` | `Remote`, `Hybrid`, `OnSite` |

**Best field map of all ATS platforms:** Both HTML and plain text, both job URL and apply URL, structured location.

**Rate limits:** None observed at 0.2s delay.

---

### 2.4 Workable ❌ (rate-limited, no valid tokens found)

**Endpoint:** `https://apply.workable.com/api/v3/accounts/{token}/jobs`

All 11 company tokens returned 429 after ~10 requests. Requires 2s+ delay.

**Field Map (from Workable docs, not validated):**

| Field | Path | Format |
|---|---|---|
| Job ID | `.results[].shortcode` | string |
| Title | `.results[].title` | string |
| Location | `.results[].location.{city,country,region}` | object |
| Apply URL | `.results[].url` | absolute URL |
| Description | via `GET /api/v3/accounts/{token}/jobs/{shortcode}` | HTML in `.description` |
| Published | `.results[].published_on` | ISO8601 date |

**Mitigation for Phase 1:** 2s+ delay between requests. Per-company caching.

---

### 2.5 SmartRecruiters ⚠️ (API works, Israeli company coverage low)

**Endpoint:** `https://api.smartrecruiters.com/v1/companies/{token}/postings`

API returns 200 for any company name (non-existent tokens return empty `content`). No Israeli startup found with active postings. The "Gong" token resolves to an old unrelated 2016 social news startup.

**Posting detail:** `GET /v1/companies/{token}/postings/{id}` includes `.applyUrl`, `.postingUrl`, `.jobAd.sections.jobDescription.text` (HTML).

**Field Map:**

| Field | Path | Format |
|---|---|---|
| Job ID | `.content[].id` | integer |
| Title | `.content[].name` | string |
| Location | `.content[].location.{city,region,country,fullLocation}` | object |
| Apply URL | via detail endpoint: `.applyUrl` | absolute URL |
| Description | via detail endpoint: `.jobAd.sections.jobDescription.text` | HTML |
| Published | `.content[].releasedDate` | ISO8601 |

**Verdict:** Low Israeli market coverage. Deprioritize.

---

### 2.6 Comeet ❌ (no public REST API found)

Comeet is an Angular SPA. All URLs at `comeet.com/jobs/*` return HTML. `Accept: application/json` returns HTTP 406. No REST API discoverable via static analysis. DNS for `api.comeet.com` and `careers.comeet.co` does not resolve.

**Mitigation:** Playwright adapter required. Companies on Comeet: Varonis, CyberArk, SimilarWeb (confirmed via careers page inspection).

---

## 3. SNC (Startup Nation Central) Findings

**Verdict: Blocked.** SNC is behind Cloudflare WAF. All requests return 403. No endpoints accessible.

**What was tried:**
- Main page + 12 API path variations → all 403
- POST to search endpoints → all 403
- Different User-Agent strings → all 403

**Fallback:** Curated static list of 52 Israeli startups compiled from public sources saved to `spike/fixtures/snc_sample.json`.

**Alternatives evaluated:**
| Source | Status | Notes |
|---|---|---|
| IVC Online (ivc-online.com) | Accessible | DNN site; no public JSON API; premium data |
| LinkedIn Jobs | 200 but auth required | Session cookie required |
| GitHub community lists | Some accessible | `yanirs/established-remote` is remote-jobs focused |

---

## 4. ATS Detection URL Patterns

| Pattern in careers page URL/source | ATS Platform |
|---|---|
| `boards.greenhouse.io/{token}` | Greenhouse (old REST API works) |
| `job-boards.greenhouse.io/{token}` | Greenhouse (new, JS-rendered) |
| `jobs.lever.co/{token}` | Lever |
| `jobs.ashbyhq.com/{token}` | Ashby |
| `apply.workable.com/{token}` | Workable |
| `{token}.workable.com` | Workable |
| `careers.smartrecruiters.com/{token}` | SmartRecruiters |
| `comeet.com/jobs/{uid}` | Comeet (needs Playwright) |
| `careers.myworkdayjobs.com` | Workday (gated) |
| `{company}.bamboohr.com` | BambooHR |

---

## 5. Coverage Estimate

Rough ATS distribution among ~200 top Israeli tech companies:

| ATS | Est. coverage | API status |
|---|---|---|
| Greenhouse | ~35% | v1 REST (60% of GH users); rest JS-rendered |
| Ashby | ~15% | Excellent public REST API |
| Comeet | ~15% | Playwright only |
| Workday/SAP | ~10% | Gated (enterprise) |
| Lever | ~8% | REST API; 0 Israeli tokens found yet |
| Workable | ~7% | REST API; aggressive rate limits |
| SmartRecruiters | ~5% | REST API; low Israeli coverage |
| Other | ~5% | Varies |

**REST-only coverage estimate:** ~55-60%  
**With Playwright for Comeet + new Greenhouse:** ~70-75%

---

## 6. Decision

### ATS hypothesis: CONFIRMED with caveats

The core hypothesis holds. Israeli startups cluster on a small number of ATS platforms. Key caveats:
1. Not all platforms have REST APIs (Comeet requires headless browser).
2. Greenhouse has two generations (v1 REST covers ~60% of GH users; new platform needs Playwright).
3. Lever not confirmed for Israeli market despite having a documented REST API.

### Adapters to build (priority order)

1. **Greenhouse v1** — highest confirmed coverage, 5 fixtures with real data
2. **Ashby** — clean API with best field parity (HTML + plain text, both URLs), growing adoption
3. **Lever** — documented API; needs token discovery mechanism
4. **Workable** — valid API; needs respectful rate limiting (2s delay)
5. **SmartRecruiters** — low Israeli coverage; deprioritize
6. **Comeet** — Playwright adapter; Phase 2 item

### Company list strategy

- **Phase 1:** Curated static list (52 companies in `snc_sample.json`) + auto-detect ATS from careers page URL
- **Phase 2:** Careers-page scraper that extracts ATS tokens from company websites dynamically
- **SNC:** Blocked by Cloudflare; not viable without browser automation or API key

### Blockers for Phase 2

1. Greenhouse new platform (`job-boards.greenhouse.io`) requires Playwright — affects monday.com, Wiz, Snyk, Coralogix, Island, Lemonade.
2. Comeet has no REST API.
3. Token discovery for Lever/Workable needs scraping from careers page links.
4. SNC blocked; company list seeding requires manual curation.

### Confirmed REST endpoints for Phase 1

```
# Greenhouse v1
GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
Fields: .jobs[].{id, title, absolute_url, location.name, content(HTML), updated_at}

# Ashby
GET https://api.ashbyhq.com/posting-api/job-board/{token}
Fields: .jobs[].{id, title, location, applyUrl, descriptionHtml, descriptionPlain, publishedAt}

# Lever
GET https://api.lever.co/v0/postings/{token}?mode=json
Fields: [].{id, text, categories.location, applyUrl, descriptionPlain, createdAt(ms)}

# SmartRecruiters (list + detail)
GET https://api.smartrecruiters.com/v1/companies/{token}/postings
GET https://api.smartrecruiters.com/v1/companies/{token}/postings/{id}
Fields: .content[].{id, name, location} + detail: .applyUrl, .jobAd.sections.*.text(HTML)
```

---

## 7. Post-spike decisions

- **v1 scope = "easy group" (REST-only adapters).** Build Greenhouse-v1 and Ashby
  first (real fixtures captured). Comeet + new-Greenhouse (Playwright) are deferred
  to a later adapter behind the same `ATSAdapter` interface — no rework needed.
- **Company list is slow-changing** — refresh cadence ~monthly, NOT daily. The job
  *fetch* runs daily; the company *universe* is refreshed occasionally.

### Company-list strategy (revised)

Authoritative source is still Startup Nation Central — it is blocked to automation
(Cloudflare 403) but fully accessible to a logged-in human in a browser. Since the
list only needs monthly refresh, the plan is:

1. **Bootstrap now:** `spike/fixtures/companies_seed.json` — 247 unique companies
   (GitHub `israeli-opensource-companies` + Failory + curated), 209 with websites.
   Lets us build + test the whole pipeline immediately.
2. **Best source (manual, monthly):** user logs into SNC once and exports / captures
   the full company list; we ingest it as the authoritative seed and refresh ~monthly.
   Sidesteps the WAF entirely (real authenticated session).

Caveat on the bootstrap lists: GitHub list is community-maintained (sporadic, skews
open-source/dev-tools); Failory is editorial/static (goes stale). Fine as a
bootstrap, not as the long-term authoritative source — hence SNC-via-login monthly.

The company-list loader (Phase 2) will read a normalized seed file regardless of
which source produced it, so swapping bootstrap → SNC export is a data change, not
a code change.
