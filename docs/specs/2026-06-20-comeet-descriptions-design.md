# Comeet Descriptions — Design Spec

**Date:** 2026-06-20
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

Give Comeet jobs real descriptions. The ~30 working Comeet companies currently have
**no job description** (Comeet's positions API doesn't return one), so they're matched
on **title only** — weak embedding similarity and almost nothing for the LLM to judge.
Fetch each position's description so those jobs match as well as Greenhouse/Ashby/Lever.

## 2. The finding (verified by spike)

- Comeet's `careers-api/2.0` returns **no description** — not in the positions list,
  not in the per-position detail endpoint (only metadata).
- The **hosted job page** (`position["url_comeet_hosted_page"]`, e.g.
  `https://www.comeet.com/jobs/{slug}/{uid}/{title}/{puid}`) embeds the full
  description as an HTML-escaped JSON string field `"description"` in the **static
  HTML** — retrievable with a plain HTTP GET (no headless browser). Confirmed: a real
  675-char description extracted from Aqua Security's hosted page.

## 3. How it works

`ComeetAdapter.fetch_jobs(company)` already fetches the positions list and builds
`Job`s without a description. We enrich it: for each position, fetch its
`url_comeet_hosted_page`, extract the embedded `"description"` JSON string, unescape
it and strip HTML tags to plain text, and set it on the `Job`. The hosted-page
fetches run **concurrently** (capped pool) so the added latency is bounded.

Result: Comeet jobs carry descriptions → improved cosine similarity, and the LLM
ranker (last-24h batch + per-job Rate) finally has real content to score for these
companies.

## 4. The concurrency decision (approved)

- **Concurrent fetch in the adapter.** For each company's positions, fetch the
  hosted pages in parallel with a capped pool (default 8) and a short per-request
  timeout (~10s). This keeps run time modest despite ~1 request per position.
- A hosted-page fetch that fails or whose format changed → that job keeps
  `description=None` (today's behavior) — never breaks the run. Per-company isolation
  in the ingestion loop already handles a wholesale failure.

## 5. Architecture (small, contained — one adapter)

- `src/startup_agent/adapters/ats/comeet.py`:
  - A pure helper `extract_description(html: str) -> str | None` — regex the embedded
    `"description":"…"` JSON string, `json.loads` to unescape, strip `<…>` tags,
    collapse whitespace, return clean text (or `None` if absent).
  - `ComeetAdapter` gains an injectable **page fetcher** `fetch_page: Callable[[str],
    str]` (defaults to an httpx GET with a browser User-Agent) so tests run offline.
  - After building the position `Job`s, fetch each position's
    `url_comeet_hosted_page` **concurrently** (a bounded `ThreadPoolExecutor`, max
    workers = a module constant, default 8) and attach the extracted description.
    The position's hosted URL is read from the raw payload (`url_comeet_hosted_page`,
    fallback `position_url`).
  - No change to the `ATSAdapter` interface, the factory, or any other adapter.
- A captured **fixture** `spike/fixtures/comeet_hosted_page.html` (one real hosted
  page) backs the extraction test — no network in tests.

## 6. Data flow

```
ComeetAdapter.fetch_jobs(company):
  GET positions list (token) → raw positions
  concurrently, per position: GET url_comeet_hosted_page → extract_description(html)
  build Job(..., description=<clean text or None>)  → list[Job]
```
Everything downstream (dedup, embedding, prefilter, LLM rescore) is unchanged — the
jobs simply now have descriptions.

## 7. Error handling

- Hosted-page GET fails / times out / non-200 → `description=None` for that job;
  warning logged; other positions and companies proceed.
- `"description"` field missing or unparseable in the HTML → `extract_description`
  returns `None`; job kept without a description.
- Total Comeet failure for a company → already caught by the ingestion loop's
  per-company isolation (the company is skipped, run continues).

## 8. Testing (offline)

- `extract_description` against the saved `comeet_hosted_page.html` fixture →
  returns clean plain-text containing expected phrases; returns `None` for HTML with
  no description field.
- `ComeetAdapter` with an injected `fetch_json` (positions) **and** a fake
  `fetch_page` (returns the fixture HTML): asserts each job gets the description; a
  `fetch_page` that raises for one position → that job has `description=None`, others
  still populated (graceful).
- Existing Comeet adapter tests keep passing (positions parsing unchanged).

## 9. Scope

**In:** Comeet description enrichment via concurrent hosted-page fetch + extraction,
graceful per-job failure, offline tests.

**Out (deferred):** caching descriptions across runs / only-new-jobs enrichment;
descriptions for any other ATS (Greenhouse/Ashby/Lever already provide them);
rendering full descriptions in the UI (the digest/cards show title + score + reason,
not the full text).

## 10. Performance note

This adds ~1 hosted-page GET per Comeet position per run (a few hundred across ~30
companies), run concurrently (pool of 8) to keep it bounded — expect a modest
increase in fetch time, not a multiplier. If it ever becomes a problem, the deferred
"only-new-jobs enrichment" is the next optimization.
