# Israeli Startup Job Agent — Design Spec

**Date:** 2026-06-12
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal, isolated from conifers)

## 1. Goal

A local, single-user tool that each day pulls newly-posted jobs from Israeli
startups, ranks them against the user's CV, and produces a digest of the
relevant ones. Fully standalone — runs on a laptop, no cloud/Azure/Conifers
infra. Python. Built to a production / portfolio-grade standard (clean
architecture, OOP, design patterns, tests).

Future work (out of scope for v1): per-job notes/memo, auto-apply,
cover-letter generation, multi-CV support, web UI, generic per-site scraper.

## 2. Core insight — ATS adapters, not per-company clients

Israeli startups overwhelmingly host careers pages on a handful of Applicant
Tracking Systems (ATS): Comeet (very common in IL), Greenhouse, Lever,
Workable, Ashby, SmartRecruiters. Each ATS exposes **one public JSON API that
serves all companies on it**. So we build ~6 adapters, not thousands of
clients. Each company needs only an `ats_type` + a `token` (its board id on
that ATS). Companies not on a known ATS are logged and skipped in v1.

## 3. "Last 24 hours" — definition

ATS posted-dates are inconsistent across providers, so they are NOT the primary
signal. Instead: **"new" = a job id we have not recorded before.** Since the
tool runs daily, "newly appeared since yesterday" ≈ last 24h, and is far more
robust than parsing heterogeneous date fields. When an ATS does provide a
reliable posted date, we store and display it.

## 4. Architecture — daily pipeline

```
Startup Nation Central list ──► Company registry (DB)
                                     │  (each company: ats_type + token)
                                     ▼
        ATS adapters (Comeet/Greenhouse/Lever/…)  ──fetch──► raw jobs
                                     ▼
                       Normalize → common Job schema
                                     ▼
        Freshness/dedup: keep only jobs NOT seen before
                                     ▼
   Stage 1 prefilter:  rules (location/seniority/keywords)
                       + CV-embedding cosine similarity   → shortlist ~15–25
                                     ▼
   Stage 2 LLM ranker: score 0–100 + one-line reason per shortlisted job
                                     ▼
        Persist matches + mark jobs seen + log run
                                     ▼
        Digest builder → renderer (markdown) → delivery (channel TBD)
```

## 5. Production architecture (hexagonal / ports & adapters)

```
domain/        pure models: Company, RawJob, Job, MatchResult, RunReport, Preferences
ports/         abstract interfaces: ATSAdapter, JobRepository, Embedder,
               Ranker, PrefilterStrategy, DigestRenderer, DeliveryChannel
adapters/
   ats/        ComeetAdapter, GreenhouseAdapter, LeverAdapter, … (implement ATSAdapter)
   storage/    SQLiteJobRepository (implements JobRepository)
   embedding/  LocalEmbedder — sentence-transformers (implements Embedder)
   delivery/   FileChannel now, EmailChannel later (implement DeliveryChannel)
services/      IngestionService, MatchingService, DigestService
   pipeline.py the daily run; composes services via dependency injection
factories/     ATSAdapterFactory (registry keyed by ats_type); wiring from config
config/        typed Settings (pydantic-settings, from .env) + preferences.yaml
cli.py         commands: discover / refresh-companies / run / show
```

Patterns:
- **Factory + registry** for ATS adapters: registry maps `ats_type → adapter`;
  iterating companies does `factory.for_company(company).fetch_jobs(company)`.
  Adding an ATS = one new class + register it, nothing else changes.
- **Repository pattern**: services depend on the `JobRepository` interface, not
  SQLite; unit tests use an in-memory fake.
- **Strategy pattern**: prefilter, ranker, and delivery are interchangeable
  implementations chosen by config.
- **Typed config + DI**: factories wire the graph at startup; nothing hard-codes
  its collaborators.
- Typed domain models, full type hints, structured logging, `pyproject.toml`
  packaging, pytest with fixture-replayed adapters.

## 6. Data model (SQLite — one `jobs.db`)

**companies** — universe of startups (from Startup Nation Central)
- id (PK), name, website, careers_url
- ats_type (`comeet`/`greenhouse`/`lever`/…/`unknown`), ats_token
- sector, size, source (`snc`), active, added_at, last_fetched_at

**jobs** — every job ever seen (powers dedup)
- id (PK = hash(company_id, ats_job_id)), company_id → companies, ats_job_id
- title, location, url, description
- posted_at (ATS date if reliable, else null), first_seen_at (the real "new" signal)
- embedding (BLOB, cached), raw_json

**cv** — the user's CV (re-embedded when changed)
- id (PK), path, text, embedding (BLOB), model, updated_at

**runs** — one row per daily execution (observability)
- id, started_at, finished_at, companies_count, jobs_fetched, jobs_new,
  jobs_matched, status (`success`/`partial`/`failed`), error

**matches** — ranked results per run (reproducible / browsable)
- id, run_id → runs, job_id → jobs, score (0–100), reason, stage, created_at

Relationships: companies 1—* jobs; runs 1—* matches; jobs 1—* matches; cv standalone.
Embeddings stored as BLOB; cosine similarity in NumPy (no vector DB at this scale).

## 7. Matching detail

- **Stage 1 (cheap, hundreds → ~20):** hard rules from `preferences`
  (location = Israel/remote, seniority band, must-have / excluded keywords)
  AND/OR cosine similarity between CV vector and each job vector. Tunable thresholds.
- **Stage 2 (quality + explanations):** Claude scores each shortlisted job
  `{score: 0–100, reason}` against the CV. Only the shortlist hits the LLM, so
  cost is bounded (~20 calls/day).
- Digest sorted by LLM score; each entry: title, company, location, score,
  one-line reason, apply link.

Embeddings: **local sentence-transformers** (no API key, offline, free), behind
the `Embedder` interface so a hosted model is a one-line swap.

## 8. Run model & delivery

- **Daily scheduled** run (cron/launchd), fetches last-24h-new jobs, matches,
  delivers a ranked digest. Idempotent: re-running the same day never
  duplicates or re-notifies.
- Digest built as **structured data + pluggable renderer** (markdown now).
  Delivery channel chosen later; v1 writes a dated local markdown file via
  `FileChannel`. Email/Slack are later channels behind `DeliveryChannel`.

## 9. Error handling

- **Per-company isolation** — one company's failure is caught/logged; the run
  continues. Counts recorded in `runs`.
- **Polite fetching** — concurrency cap + retry/backoff per ATS.
- **LLM failures** — retry; a job that fails scoring is shown unranked, not
  silently dropped.
- **Empty-run alarm** — a run that fetches 0 jobs (likely broken adapter) is
  flagged, not treated as "no new jobs."

## 10. Config & secrets (all local)

`.env` (gitignored): LLM API key, thresholds, delivery creds.
`preferences.yaml`: roles, seniority, locations, must-have / excluded keywords.
CV: a local file (`Downloads/Netanel_Sade.pdf`), parsed to text once, embedded.

## 11. Testing

- ATS adapters tested against **recorded fixtures** (real ATS JSON captured in
  Phase 0, replayed offline — no network in tests).
- Unit tests: normalization, dedup, cosine, digest rendering.
- One end-to-end test on a tiny fixture DB.
- TDD throughout.

## 12. Git / environment isolation (done)

- Repo at `~/projects/startup-agent`, remote
  `git@github-personal:nathanielsade/startup-agent.git` via an isolated SSH
  host alias + dedicated key `id_ed25519_personal`.
- Conifers (`github.com` + `id_ed25519` → netanelSade1) untouched. Per-folder
  routing; no global config changed. Only `~/.ssh/config` was appended to
  (backed up).

## 13. Build phases

- **Phase 0 — Discovery spike:** sample SNC; for ~10–20 companies detect ATS and
  hit its API; record fixtures; measure ATS coverage %. Validates the approach
  and decides adapter build order before committing.
- **Phase 1 — Skeleton:** SQLite schema + repo layer, config, CLI scaffold, models, packaging.
- **Phase 2 — Ingestion:** SNC loader + ATS detection + top-coverage adapters;
  normalize + dedup. End-to-end "today's new jobs land in DB."
- **Phase 3 — Matching:** CV parse + embed; stage-1 prefilter; stage-2 LLM ranker.
- **Phase 4 — Digest + delivery:** builder + markdown renderer; local-file delivery.
- **Phase 5 — Scheduling:** cron/launchd entry, idempotency, empty-run alerting.

## 14. Open questions

1. Company-list refresh cadence (weekly refresh of SNC vs daily job fetch) — assumed weekly.
2. Personal git commit email — pending.
3. Hard preferences (roles, seniority, locations, must-have/excluded skills) — pending from user.
