# Cloud Migration — Phase 1: Foundation (DB + Auth + Data Model)

**Date:** 2026-06-21
**Status:** Approved design (pending user review), pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 0. Where Phase 1 sits

Turning the local single-user tool into a multi-user cloud product is a 5-phase effort
(Foundation → Batch → Matching refactor → Frontend auth/tracking → Deploy). **Phase 1
builds only the foundation everything else needs:** a multi-user Postgres database
(Supabase), Supabase Auth, the per-user data model, and a Postgres storage adapter
behind the existing ports. After Phase 1 the app runs locally against Postgres with
real per-user isolation and login — but the background batch, the precompute matching,
the auth UI, and deployment come in later phases.

## 1. Goal

The API authenticates users via Supabase, stores all data in Postgres (shared
jobs/companies + per-user CV/prefs/profile/tracking/events), and isolates every user's
data by their Supabase user id. Local dev/tests run against a local Postgres.

## 2. Platform decisions (settled in brainstorming)

- **Database + Auth: Supabase** (managed Postgres + built-in Auth, free tier; region
  Frankfurt/EU). One service for both; plain Postgres, so it scales to paid tiers with
  no rewrite.
- **Cost:** $0 on the free tier (≈500 MB DB, ample auth) — our data is tiny (job
  embeddings ≈25 MB). The only recurring cost is the LLM (later phases), ~$0.50/active
  user/mo with Haiku + caps.
- **Embeddings:** stored as a column; cosine stays **in-app** (same as today). pgvector
  is a deferred optimization, not used in Phase 1.
- **Postgres everywhere:** cloud = Supabase; local dev/test = a local Postgres
  (Docker). The current SQLite adapter is retired as the runtime store (the existing
  hexagonal ports make this a drop-in swap).

## 3. User actions required (one-time, by the human)

1. Create a Supabase project (free tier), region EU/Frankfurt.
2. Copy into a local `.env` (and later into deploy secrets): `SUPABASE_URL`,
   `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`,
   `DATABASE_URL` (Postgres connection string), plus `ANTHROPIC_API_KEY` /
   `OPENAI_API_KEY`.
3. Enable email/password auth in Supabase (Google OAuth is a later toggle).

(Implementation can run fully against a local Docker Postgres until these exist; only
the live auth-token verification needs the real `SUPABASE_JWT_SECRET`.)

## 4. Data model

### Shared (one copy for all users)
- **`companies`** — current fields (name, website, careers_url, ats_type, ats_token,
  sector, size, source, active, linkedin_url, added_at, last_fetched_at).
- **`jobs`** — current fields (id, company_id, ats_job_id, title, location, url,
  description, posted_at, first_seen_at) **plus**:
  - `embedding` (float array) — the matching vector
  - `embed_model` (text) — which model produced it (CV + jobs must match)
  - `last_seen_at` (timestamptz) — last batch run that returned it
  - `active` (bool) — soft-retire flag (never hard-delete jobs users referenced)

### Per user (keyed by Supabase `user_id` UUID)
- **`user_profiles`** — `user_id` (PK), `cv_text`, `cv_embedding` (float array),
  `embed_model`, `cv_uploaded_at`, `preferences` (jsonb), `applicant_profile` (jsonb).
- **`user_jobs`** — (`user_id`, `job_id`) PK; `status`
  (`new`/`seen`/`saved`/`applied`/`dismissed`); `job_snapshot` (jsonb: title, company,
  url — so history survives job retirement); `llm_score` (int), `llm_reason` (text),
  `scored_at`; `updated_at`. (This is both the tracking state **and** the per-user LLM
  cache.)
- **`llm_usage`** — (`user_id`, `day`) PK, `count` — enforces the per-user daily cap.
- **`events`** — append-only: `id`, `user_id`, `event_type`
  (`search_run`/`job_shown`/`job_viewed`/`job_rated`/`application_opened`/
  `marked_applied`/`status_changed`/`dismissed`), `job_id` (nullable), `metadata`
  (jsonb), `created_at`. The analytics backbone for a future dashboard.

Schema is created/migrated by a SQL file run on `init_schema()` (mirrors today's
`schema.sql` approach), `CREATE TABLE IF NOT EXISTS` + additive `ALTER`s.

## 5. Architecture / components

- **`adapters/storage/postgres_repository.py` (new)** — `PostgresJobRepository`
  implementing the existing `JobRepository` port (companies + jobs + lifecycle). Uses
  `psycopg`/SQLAlchemy Core; reads `DATABASE_URL`.
- **`ports/user_repository.py` (new)** + **`adapters/storage/postgres_user_repository.py`
  (new)** — a `UserRepository` port for per-user data (`get/save_profile`,
  `get/save_preferences`, `get/save_cv`, `get/set_job_state`, `record_event`,
  `bump_llm_usage`/`get_llm_usage`). Splitting shared vs per-user keeps each repo
  focused.
- **`api/auth.py` (new)** — `get_current_user()` FastAPI dependency: reads the
  `Authorization: Bearer <jwt>` header, verifies it with `SUPABASE_JWT_SECRET` (HS256),
  returns the `user_id` (UUID). Raises 401 on missing/invalid token.
- **Routes** — every data route gains `user = Depends(get_current_user)` and scopes its
  reads/writes to that user. The single-tenant `get_cv()`/preferences/profile endpoints
  become per-user via `UserRepository`. Shared job/company reads need auth too (so only
  signed-in users hit the API) but aren't user-scoped.
- **`config/settings.py`** — add `database_url`, `supabase_url`, `supabase_jwt_secret`,
  `supabase_anon_key`, `supabase_service_role_key`; LLM keys already present. Drop the
  in-memory `llm_config` / bring-your-own-key path (server-side key now).

## 6. Data flow (after Phase 1, before later phases)

```
React → (Supabase Auth JWT) → FastAPI (verify JWT → user_id)
   • per-user reads/writes (CV, prefs, profile, tracking, events) → user tables
   • shared reads (companies, jobs) → shared tables
Jobs are still ingested by the existing run/match paths for now; the GitHub-Actions
batch that pre-embeds everything is Phase 2.
```

## 7. Error handling

- Missing/invalid/expired JWT → `401`.
- DB connection failure → `503` with a clear message; no silent data loss.
- A job referenced by a `user_jobs` row is **never hard-deleted** — retirement sets
  `active=false`; the `job_snapshot` keeps the applied-to record meaningful.
- All per-user writes are scoped by `user_id`; no cross-user reads possible.

## 8. Testing

- **Port-contract tests** for `PostgresJobRepository` + `PostgresUserRepository` against
  a **local Docker Postgres** (spun up in CI/dev): round-trip companies/jobs/embeddings,
  per-user CV/prefs/profile, job-state, events, usage counter, and user isolation
  (user A can't see user B's data).
- **Auth dependency tests**: a valid signed JWT → user_id; missing/garbage/expired → 401
  (sign test tokens with a test `SUPABASE_JWT_SECRET`).
- Existing service/matching unit tests keep running against the repository ports
  (unchanged behavior).

## 9. Scope

**In:** Supabase platform decision + setup doc; the Postgres schema (shared + per-user
incl. events); `PostgresJobRepository` + `UserRepository`/adapter; JWT auth dependency +
route protection; config/secrets; tests against local Postgres.

**Out (later phases):** GitHub-Actions batch + lifecycle automation (P2); precompute
matching refactor + capped auto-LLM-rank + budget guardrail (P3); frontend auth UI +
tracking UI + dashboard (P4); deployment, CORS, rate-limiting (P5); payments, Google
OAuth, account-deletion UI (post-MVP).

## 10. Open choice carried into the plan

Where the **CV is embedded** at upload: the web service loads the embedding model and
embeds on upload (simple, immediate match, but carries the torch dependency on the API
host). This is the leaning; revisit at deploy (P5) if the host RAM is tight.
