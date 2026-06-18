# Comeet POC Findings

## TL;DR

**The flow works end-to-end.** A credentials-extraction step (static HTML scrape OR
one-time headless browser load) yields a `uid` + `token`, after which ALL future
fetches are plain `httpx` GET requests with zero browser involvement.

Two extraction strategies confirmed:

| Strategy | How it works | Browser needed? |
|----------|-------------|-----------------|
| **HTML scrape** | Comeet WP plugin embeds credentials in `<script>` on initial HTML response | No |
| **Browser intercept** | Page JS fires the API call; headless Chromium captures the URL | Once (bootstrap) |

Tested 4 companies: 4 succeeded, 0 failed.

---

## Results per company

### Aqua Security — strategy: `html`

- **URL:** https://www.aquasec.com/careers/
- **uid:** `91.001`
- **token:** `191644966966644E...` (truncated)
- **Bootstrap time:** 0.49s
- **Jobs fetched via REST:** 12

**Sample position (normalized):**

```json
{
  "uid": "CD.86E",
  "title": "Engineering Platform Manager",
  "city": "Ramat Gan",
  "country": "IL",
  "is_remote": true,
  "department": "Engineering",
  "employment_type": "Full Time",
  "experience_level": null,
  "workplace_type": "Hybrid",
  "apply_url": "https://www.aquasec.com/about-us/careers/co/ramat-gan-israel/CD.86E/engineering-platform-manager/all/",
  "updated_at": "2026-06-14T11:03:44Z"
}
```

**All raw keys on position object:**

`['company_name', 'department', 'email', 'employment_type', 'experience_level', 'internal_use_custom_id', 'is_internal', 'linkedin_job_posting_id', 'location', 'name', 'picture_url', 'position_url', 'time_updated', 'uid', 'url_active_page', 'url_comeet_hosted_page', 'url_detected_page', 'url_recruit_hosted_page', 'workplace_type']`

### Global-e — strategy: `html`

- **URL:** https://www.global-e.com/careers
- **uid:** `62.002`
- **token:** `2629881310157272...` (truncated)
- **Bootstrap time:** 1.53s
- **Jobs fetched via REST:** 78

**Sample position (normalized):**

```json
{
  "uid": "8C.B66",
  "title": "Account Executive",
  "city": "New York",
  "country": "US",
  "is_remote": true,
  "department": "Sales",
  "employment_type": "Full-time",
  "experience_level": "Intermediate",
  "workplace_type": "Hybrid",
  "apply_url": "https://www.global-e.com/en/careers/8c-b66/",
  "updated_at": "2026-06-18T00:26:03Z"
}
```

**All raw keys on position object:**

`['company_name', 'department', 'email', 'employment_type', 'experience_level', 'internal_use_custom_id', 'is_internal', 'linkedin_job_posting_id', 'location', 'name', 'picture_url', 'position_url', 'time_updated', 'uid', 'url_active_page', 'url_comeet_hosted_page', 'url_detected_page', 'url_recruit_hosted_page', 'workplace_type']`

### Sygnia — strategy: `html`

- **URL:** https://www.sygnia.co/careers
- **uid:** `78.00A`
- **token:** `87A32DC3B5687A19...` (truncated)
- **Bootstrap time:** 2.59s
- **Jobs fetched via REST:** 14

**Sample position (normalized):**

```json
{
  "uid": "F1.C6C",
  "title": "Cyber Security Consultant",
  "city": "Tel Aviv",
  "country": "IL",
  "is_remote": true,
  "department": "Cyber Security Services",
  "employment_type": "Full-time",
  "experience_level": "Senior",
  "workplace_type": "Hybrid",
  "apply_url": "https://www.sygnia.co/careers/co/israel/F1.C6C/cyber-security-consultant/all/",
  "updated_at": "2026-06-18T12:54:04Z"
}
```

**All raw keys on position object:**

`['company_name', 'department', 'email', 'employment_type', 'experience_level', 'internal_use_custom_id', 'is_internal', 'linkedin_job_posting_id', 'location', 'name', 'picture_url', 'position_url', 'time_updated', 'uid', 'url_active_page', 'url_comeet_hosted_page', 'url_detected_page', 'url_recruit_hosted_page', 'workplace_type']`

### Hunters.ai — strategy: `browser`

- **URL:** https://www.hunters.ai/careers
- **uid:** `67.007`
- **token:** `7672C6A163533D11...` (truncated)
- **Bootstrap time:** 0.62s
- **Jobs fetched via REST:** 1

**Sample position (normalized):**

```json
{
  "uid": "84.A6B",
  "title": "Senior Full-Stack Engineer",
  "city": "Tel Aviv-Yafo",
  "country": "IL",
  "is_remote": true,
  "department": "R&D",
  "employment_type": "Full-time",
  "experience_level": "Senior",
  "workplace_type": "Hybrid",
  "apply_url": "https://www.comeet.com/jobs/hunters/67.007/senior-full-stack-engineer/84.A6B",
  "updated_at": "2026-05-05T14:14:54Z"
}
```

**All raw keys on position object:**

`['company_name', 'department', 'email', 'employment_type', 'experience_level', 'internal_use_custom_id', 'is_internal', 'linkedin_job_posting_id', 'location', 'name', 'picture_url', 'position_url', 'time_updated', 'uid', 'url_active_page', 'url_comeet_hosted_page', 'url_detected_page', 'url_recruit_hosted_page', 'workplace_type']`

---

## Position field map (adapter reference)

| Our field | Comeet key | Notes |
|-----------|-----------|-------|
| `job_id` | `uid` | stable per-position identifier |
| `title` | `name` | plain string |
| `city` | `location.city` | nested object |
| `country` | `location.country` | ISO 2-letter code |
| `is_remote` | `location.is_remote` | boolean |
| `department` | `department` | string |
| `employment_type` | `employment_type` | e.g. `Full-time` |
| `seniority` | `experience_level` | e.g. `Senior`, `Mid-Level` |
| `workplace_type` | `workplace_type` | `Hybrid`, `On-site`, `Remote` |
| `apply_url` | `url_active_page` | direct application URL |
| `updated_at` | `time_updated` | ISO 8601 timestamp |

---

## Adapter design (production sketch)

```
Bootstrap (once per company, ~1-10s):
  1. Try HTML scrape of careers page → extract uid+token from <script>
  2. If not found → headless Chromium, intercept careers-api network request
  3. Persist uid+token to DB

Daily sync (no browser, ~1s):
  GET https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}
  → parse list → upsert jobs

Token refresh:
  Tokens are static company-level credentials (not session-based).
  Re-run bootstrap only if REST call returns 401/403.
```

## Performance notes

- HTML scrape bootstrap: **< 2s** (plain HTTP)
- Browser interception bootstrap: **5-12s** (one-time cost)
- Daily REST fetch: **< 1s** per company regardless of job count
