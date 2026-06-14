# ATS Detection Pass 2

**Date:** 2026-06-12

## Input State

| Metric | Count |
|--------|-------|
| Total unknowns going in | 724 |
| Total attempted | 724 |
| Newly resolved | 145 |
| Still unknown | 579 |

## Newly Detected by ATS

| ATS | Newly Detected |
|-----|---------------|
| comeet | 81 |
| greenhouse | 16 |
| workday | 10 |
| lever | 8 |
| workable | 7 |
| teamtailor | 7 |
| bamboohr | 6 |
| ashby | 5 |
| recruitee | 2 |
| rippling | 2 |
| smartrecruiters | 1 |
| **Total** | **145** |

## Grand Totals After Pass 2

| ATS | Total Companies |
|-----|----------------|
| unknown | 579 |
| greenhouse | 120 |
| comeet | 81 |
| ashby | 56 |
| lever | 38 |
| workday | 10 |
| workable | 7 |
| teamtailor | 7 |
| bamboohr | 6 |
| recruitee | 2 |
| rippling | 2 |
| smartrecruiters | 1 |
| **Known total** | **330** |

## ATS API Reachability

| ATS | Has API? | Notes |
|-----|----------|-------|
| **greenhouse** | Yes | Public Jobs API at `boards-api.greenhouse.io/v1/boards/{token}/jobs` — no auth required |
| **ashby** | Yes | Public jobs endpoint at `jobs.ashbyhq.com/{token}` + JSON API |
| **lever** | Yes | Public postings API at `api.lever.co/v0/postings/{token}` — no auth required |
| workable | Partial | Read API requires OAuth; public job widget embeds are scrapable |
| smartrecruiters | Partial | Public careers page, no official unauthenticated jobs API |
| comeet | No | No public API; scraping only |
| workday | No | Tenant-specific portal, no unified public API |
| teamtailor | Partial | REST API exists but requires API key per tenant |
| bamboohr | No | Requires company-specific API key |
| recruitee | Partial | Public job listings page; REST API requires auth |
| rippling | No | No public jobs API |

## Detection Method Notes

- Crawl strategy: homepage → extract careers/jobs anchor links (up to 5) + hardcoded `/careers`, `/jobs` paths + `careers.{domain}`, `jobs.{domain}` subdomains
- ATS detection: substring/regex match against final redirect URL and full HTML source
- Concurrency: 15 async workers, 8s timeout per request
- SSL verification disabled to reduce false-negative skips
- Errors (timeout, connection refused, SSL, 4xx/5xx) logged to stderr and left as unknown
- ~1116 skipped URL attempts across 724 companies (mostly dead subdomains and 404 paths — expected)
