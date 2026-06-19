# Smart LLM Matching — Design Spec

**Date:** 2026-06-19
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

Add LLM fit-scoring (0–100 + a one-line "why it fits" reason) on top of the free
embedding pipeline — **automatically for jobs posted in the last 24 hours**, and
**on-demand per job** via a "Rate" button in the results list. Provider-pluggable
(Anthropic or OpenAI), API key read from `.env`, local, with no API-key UI and no
stored secret. Free embedding ranking remains the default; the LLM is an additive
quality layer.

## 2. Key & provider

- **Key from `.env`** only: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. No key field
  in the UI, no secret persisted by the app.
- **`LLM_PROVIDER`** setting = `anthropic` | `openai` (default `anthropic`) selects
  the ranker implementation. Both implement the existing `Ranker` port:
  - `ClaudeRanker` (already exists) — extended to accept preferences.
  - `OpenAIRanker` (new) — uses the `openai` SDK with a configurable base URL
    (`OPENAI_BASE_URL`), so it also works with Azure OpenAI / OpenRouter / other
    OpenAI-compatible endpoints.
- **No key/provider configured → LLM features are off**: runs fall back entirely to
  free embedding ranking; the Rate endpoint returns a clear "no LLM configured"
  error. The tool stays fully usable with no key.

## 3. Two ways the LLM is used

- **Batch (automatic, during a run):** after embedding ranking produces the match
  list, the LLM scores **only jobs posted within the last `LLM_RECENT_HOURS`
  (default 24)** — the small fresh set acted on daily. Bounded cost (~cents) and
  latency (~20–30s). Older matches keep their embedding score. Skipped entirely if
  no ranker is configured.
- **On-demand (manual):** a **"✨ Rate" button** on any result card triggers a
  single LLM call scoring *that one job* against the CV + preferences; the card
  updates in place with the fit score + reason. ~1s, a fraction of a cent.

## 4. How the two scores combine

Embedding similarity (a 0–1 cosine, shown ×100) and the LLM fit score (0–100
judgment) are different scales with different meaning, so they are **not blindly
intermixed in one sort order**. The results list is ordered:

1. **LLM-rated jobs first** — the last-24h batch plus any the user clicked "Rate" —
   sorted by LLM fit descending, each shown with a **✨ badge + reason line**.
2. **Then embedding-ranked matches** — sorted by similarity, shown as today.

The user's **preferences are injected into the LLM prompt** (e.g. "candidate wants
junior–mid backend/AI roles, ≤3 years, Center/remote — score this job's fit"), so
the LLM judges against the user's actual profile, not generically.

## 5. Architecture (fits existing ports-&-adapters layers)

- **ports** (`ports/ranker.py`): `Ranker.rank(cv_text, jobs, preferences)` — extend
  the signature to pass preferences. A shared prompt-builder (CV + prefs + job)
  is used by both ranker implementations to keep prompts consistent.
- **adapters/ranking:**
  - `claude_ranker.py` (exists) — extended for the preferences arg + shared prompt.
  - `openai_ranker.py` (new) — `OpenAIRanker(Ranker)` using the `openai` SDK,
    structured JSON output (`{score, reason}`), configurable model + base URL.
- **api/deps.py:** `get_ranker() -> Ranker | None` — builds the configured ranker
  from settings (provider + key), or `None` when no key is present.
- **services:** `services/recent_rescore.py` — `rescore_recent(matches, repo,
  ranker, preferences, recent_hours, now)` takes the embedding match list, selects
  the jobs posted within `recent_hours`, LLM-scores them, and returns the merged
  result list (LLM-rated first, then the rest). Per-job failures are caught: that
  job keeps its embedding score.
- **api routes:**
  - `run` (GET, SSE) — after computing embedding matches, if a ranker is
    configured, apply `rescore_recent` before emitting the final `done` payload;
    emit a `{stage:"rating", count}` progress event so the UI shows it.
  - **`POST /api/rate`** (new) — body `{job_id}` → load the job + CV + preferences →
    one ranker call → `{score, reason}`. Returns `400` if no ranker is configured
    or the CV is missing.
- **frontend:**
  - `api/client.ts`: `JobMatch` gains `job_id`, optional `reason`, and a `rated`
    boolean; add `rateJob(jobId) -> {score, reason}`.
  - `JobCard.tsx`: when `rated`/`reason` present, show the LLM score + reason +
    a ✨ badge; otherwise show similarity % and a "✨ Rate" button that calls
    `rateJob` and updates the card (with a loading + error state).
- **config/settings.py:** add `llm_provider: str = "anthropic"`,
  `openai_api_key: str = ""`, `openai_model: str = "gpt-4o"`,
  `openai_base_url: str = ""`, `llm_recent_hours: int = 24`. (`anthropic_api_key`
  and `llm_model` already exist.)

## 6. Data flow

```
Run (GET /api/run):
  fetch → hard prefilter(prefs) → embed → cosine + soft(prefs) → match list
        → if ranker configured: rescore_recent(last 24h jobs → LLM score+reason)
        → done payload: LLM-rated first (✨ + reason), then similarity-ranked

Rate (POST /api/rate {job_id}):
  load job + CV + prefs → ranker.rank(cv, [job], prefs) → {score, reason}
        → card updates in place
```

## 7. Error handling

- **No key/provider** → batch rescore skipped (all embedding); `/api/rate` → `400`
  "No LLM configured"; the Rate button surfaces that message.
- **LLM call fails for a job (batch)** → that job retains its embedding score; error
  logged; the run never fails because of rating.
- **LLM call fails (Rate)** → the card shows an inline error; the list is unaffected.
- **Malformed LLM output** → validated against a `{score:int 0–100, reason:str}`
  schema; on failure the job keeps its embedding score (batch) or the card shows an
  error (Rate).
- **Cost guard** → the automatic batch is recency-bounded (last 24h only), so cost
  cannot scale with backlog size.

## 8. Testing

- **Rankers:** `ClaudeRanker` and `OpenAIRanker` with **mocked clients** (no network,
  no key) — score+reason parsing, preferences present in the prompt, malformed
  output handled.
- **Provider selection:** `get_ranker()` returns the right implementation per
  `LLM_PROVIDER`, and `None` when no key is set.
- **Recency rescore:** only last-24h jobs are LLM-scored; merge ordering correct
  (LLM-rated first); a failing job keeps its embedding score.
- **API:** `POST /api/rate` via `TestClient` with a mocked ranker (valid result +
  no-key → 400); `run` honors the rescore when a ranker is injected.
- **Frontend:** `JobCard` renders rated (score+reason+✨) vs unrated (% + Rate
  button); the Rate button calls the API and updates the card.

All backend tests run offline with mocked rankers — no API key required to build or test.

## 9. Scope

**In:** provider-pluggable LLM ranking (Anthropic + OpenAI behind the `Ranker`
port), automatic batch scoring of last-24h jobs, per-job on-demand "Rate" button,
reasons shown in the UI, preferences injected into the prompt, `.env` key handling.

**Out (deferred):** CV→preferences auto-fill (separate follow-up, already specced as
prefs Phase 2); UI key entry / saved keys; cloud hosting / multi-user; using the LLM
to fetch or filter (it only scores).

## 10. Visual design

LLM-rated cards in the existing Light-SaaS style get a small **✨ "AI-rated" badge**,
the fit score in the indigo score pill, and a muted **reason line** under the meta.
Unrated cards show the similarity % pill and a subtle **"✨ Rate"** text button;
while rating, the button shows a spinner; on error, an inline red note. LLM-rated
jobs render in a top group, similarity-ranked jobs below.
