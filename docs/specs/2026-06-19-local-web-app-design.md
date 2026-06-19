# Local Web App — Design Spec

**Date:** 2026-06-19
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

A local website for the job agent: upload a CV → click "Find jobs" → watch a
live progress bar while it fetches + matches → see ranked job cards
(score · title · company · location · age · apply link). Runs on the user's Mac,
free, no API key, no cloud. Reuses the existing engine unchanged; the CLI keeps
working exactly as today.

## 2. Architecture — three cleanly-separated layers

```
frontend/  (React + Vite + TypeScript)   UI; speaks only HTTP/JSON to /api/*
   ↓ HTTP / SSE
api/       (FastAPI, thin routes)         parse request → call a service → return JSON
   ↓ function calls
src/startup_agent/  (existing engine)     domain · ports · adapters · services · factories
                                          (ATS adapters, matching, SQLite) — UNCHANGED
```

- **`frontend/` knows nothing about Python** — it only calls `/api/*`. The UI is
  fully swappable without touching the backend.
- **`api/` routes are thin** — they parse the HTTP request, invoke a **service**,
  and return JSON. No business logic in routes. Routes are the new inbound
  adapter, consistent with the project's ports-&-adapters style.
- **`src/startup_agent/` is untouched** (one tiny additive exception, §6). The CLI
  and the web both call the **same services**.

Stack: React + Vite + TypeScript (frontend); FastAPI + uvicorn (api); the existing
Python 3.13 engine.

## 3. Repository hierarchy

```
startup-agent/
├── src/startup_agent/        LAYER 3 — core engine (unchanged)
│     domain / ports / adapters / services / factories / cli.py
│
├── api/                      LAYER 2 — web routes (new, thin)
│     main.py                   FastAPI app + startup wiring
│     deps.py                   builds repo + services, injects them
│     schemas.py                request/response models (the API contract)
│     routes/
│       health.py               GET  /api/health
│       cv.py                    POST /api/cv
│       run.py                   POST /api/run     (SSE progress stream)
│       results.py               GET  /api/results
│
└── frontend/                 LAYER 1 — the UI (new, React + Vite + TS, fully separate)
      index.html · package.json · vite.config.ts · tsconfig.json
      src/
        main.tsx · App.tsx
        components/  CvUpload.tsx · RunProgress.tsx · JobCard.tsx · JobList.tsx
        api/client.ts            typed calls to /api/*  + EventSource for progress
        styles/                  design tokens + component styles
```

## 4. API contract

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET  | `/api/health` | liveness | `{status:"ok"}` |
| POST | `/api/cv` | upload PDF (multipart), parse + embed + store | `{status:"ready", chars:N}` |
| GET  | `/api/run` | fetch all companies + match; stream progress | `text/event-stream` (SSE) |
| GET  | `/api/results` | last run's ranked matches | `{matches:[JobMatch...], generated_at}` |

**SSE event shapes** (`/api/run`):
```
{ "stage": "fetching", "done": 41, "total": 249, "company": "Cato", "jobs_fetched": 1268 }
{ "stage": "matching", "candidates": 143 }
{ "stage": "done", "matched": 8 }
{ "stage": "error", "message": "..." }            # on a run-level failure
```

**JobMatch JSON** (results + final payload): `{ title, company, location, score,
posted_at, age_label, url }`. `score` is the similarity score scaled to 0–100.

## 5. Data flow

1. **Upload** — `POST /api/cv` with the PDF → `read_pdf_text` → `LocalEmbedder` →
   `repo.save_cv(...)`. Responds `ready`.
2. **Run** — `GET /api/run` (GET so the browser's native `EventSource` can consume
   it; no request body needed since the CV is already stored):
   - A background thread runs `IngestionService.run(progress=cb)` over all
     companies; `cb` pushes `{stage:"fetching", done, total, company, jobs_fetched}`
     events onto a `queue.Queue`.
   - When ingestion finishes, the thread runs `SimilarityMatchingService.run()`,
     emits `{stage:"matching", candidates}`, then `{stage:"done", matched}`.
   - The SSE endpoint drains the queue and streams each event to the browser.
   - React's `EventSource` updates the progress bar + counters on every event, so
     the UI is never frozen.
3. **Results** — on `done`, the page renders ranked `JobCard`s. Matches are also
   retrievable via `GET /api/results` (re-show the last run).

## 6. The one engine change (additive, backward-compatible)

`IngestionService.run()` gains an optional `progress: Callable[[dict], None] | None = None`.
When provided, it is called once per company with
`{done, total, company, jobs_fetched, jobs_new}`. When omitted, behavior is
identical to today — the CLI and all existing tests are unaffected.

## 7. Error handling

- **Per-company failure** — already caught/logged by the engine; the run continues.
  The progress UI may show a small "N skipped" note (derived from the run's
  partial status / failure count).
- **No CV uploaded when Run is clicked** — `/api/run` returns `400` with a clear
  message; the UI prompts the user to upload first.
- **Run-level failure** — the background thread emits `{stage:"error", message}`;
  the SSE stream forwards it; the UI shows the error instead of a frozen bar.
- **CORS** — in dev the Vite server (`:5173`) and FastAPI (`:8000`) are different
  origins; the API enables CORS for `localhost` dev origins.

## 8. Testing

- **`api/` routes** — FastAPI `TestClient`, fully offline: inject a fake
  `ATSAdapterFactory` (returns fixture jobs) and a fake/stub embedder via `deps`
  overrides. Assert: `/api/cv` stores a CV; `/api/run` streams a terminal `done`
  event with a match count; `/api/results` returns the documented JSON shape;
  `/api/run` with no CV returns `400`.
- **Engine** — existing 94 tests stay green; add one test that the new `progress`
  callback fires once per company and the no-callback path is unchanged.
- **Frontend** — kept light (personal tool): a basic render/smoke test of the
  three states. The substantive coverage lives in the API + engine tests.

## 9. Run / dev experience

- Backend: `uvicorn api.main:app --reload` (port 8000).
- Frontend: `npm run dev` (Vite, port 5173, proxies `/api` → 8000).
- A `make dev` (or a small script) starts both with one command.
- Open `http://localhost:5173`.

## 10. Scope

**In (v1):** single-user, local, free, no key. The upload → run → results flow
with a live SSE progress bar. Light-SaaS visual design (off-white background,
indigo accent, soft rounded cards, system sans-serif).

**Out (deferred):** LLM scoring in the UI; user-supplied API keys; provider-generic
ranker in the web; public cloud hosting; scheduled pre-fetch; email/Slack
delivery; authentication/multi-user. None are needed for the local single-user
tool, and each slots cleanly onto the existing interfaces later.

## 11. Visual design

Direction **"Light SaaS"**: off-white app background (~`#f7f8fa`), white cards
with soft shadow + ~14px radius, a single indigo brand accent (~`#4f46e5`),
system sans-serif, generous whitespace. Score shown as an indigo pill; apply as a
primary button. Three page states share one header (brand + run summary
"N companies · M matches"). Avoid generic AI-template aesthetics — distinctive,
clean, product-like.
