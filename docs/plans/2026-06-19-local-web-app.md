# Local Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A local website — upload CV → click Find jobs → watch a live progress bar while it fetches + matches → see ranked job cards with apply links. Reuses the existing engine; CLI unaffected.

**Architecture:** 3 layers — `frontend/` (React+Vite+TS) → `api/` (thin FastAPI routes, SSE for progress) → `src/startup_agent/` (existing engine, one additive change). Routes parse requests and call existing services; the UI speaks only HTTP/JSON to `/api/*`.

**Tech Stack:** FastAPI + uvicorn (api), React + Vite + TypeScript (frontend), the existing Python 3.13 engine. Backend tested offline with FastAPI `TestClient` + injected fakes.

**Repo discipline:** Work ONLY in `/Users/netanelsade/projects/startup-agent`; never touch `/Users/netanelsade/conifers`. Branch `phase-6/local-web`. Commit messages end with the co-author trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File structure (new)

```
api/
  __init__.py
  main.py            FastAPI app, CORS, router mounting
  deps.py            get_settings / get_repo / get_embedder / get_factory (overridable in tests)
  schemas.py         JobMatch + response models; to_job_match() helper
  matching_view.py   compute_matches(repo, embedder, prefs, threshold) -> list[JobMatch]
  routes/
    __init__.py
    health.py        GET  /api/health
    cv.py            POST /api/cv
    run.py           GET  /api/run    (SSE)
    results.py       GET  /api/results
tests/api/
  __init__.py
  conftest.py        client fixture + dependency overrides (fake factory/embedder, tmp db)
  test_health.py
  test_cv.py
  test_run.py
  test_results.py
frontend/
  package.json  vite.config.ts  tsconfig.json  index.html
  src/
    main.tsx  App.tsx
    api/client.ts
    components/CvUpload.tsx  RunProgress.tsx  JobCard.tsx  JobList.tsx
    styles/tokens.css  app.css
Makefile             `make dev` runs both servers
```

---

### Task 1: Web dependencies + api package + health route

**Files:** Create `api/__init__.py`, `api/main.py`, `api/routes/__init__.py`, `api/routes/health.py`, `tests/api/__init__.py`, `tests/api/conftest.py`, `tests/api/test_health.py`. Modify `pyproject.toml` (via uv).

- [ ] **Step 1: Add deps**

Run: `cd /Users/netanelsade/projects/startup-agent && uv add fastapi uvicorn python-multipart && uv add --dev httpx`
(`httpx` is needed by FastAPI's TestClient; it may already be present — harmless.)

- [ ] **Step 2: Write the failing test** (`tests/api/test_health.py`)

```python
def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Minimal conftest** (`tests/api/conftest.py`) — full overrides come in later tasks; for now just a client:

```python
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: FAIL (`ModuleNotFoundError: api.main`)

- [ ] **Step 5: Implement** `api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

`api/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health

app = FastAPI(title="Startup Job Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
```

Create empty `api/__init__.py`, `api/routes/__init__.py`, `tests/api/__init__.py`.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/api/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add api tests/api pyproject.toml uv.lock
git commit -m "feat: add FastAPI api package + health route" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Progress callback on IngestionService (engine change, TDD)

**Files:** Modify `src/startup_agent/services/ingestion.py`; Test `tests/services/test_ingestion.py` (append).

- [ ] **Step 1: Write the failing test** (append to `tests/services/test_ingestion.py`)

```python
def test_ingestion_progress_callback_fires_per_company():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    events = []
    IngestionService(repo=repo, factory=factory).run(progress=events.append)
    # one event per company (3 seeded), each carrying counters
    assert len(events) == 3
    assert events[0]["total"] == 3
    assert {"done", "total", "company", "jobs_fetched", "jobs_new"} <= events[-1].keys()
    assert events[-1]["done"] == 3
```

(Reuses the existing `_seeded_repo` and `_routing_fetcher` helpers already in this test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/services/test_ingestion.py::test_ingestion_progress_callback_fires_per_company -v`
Expected: FAIL (`run()` takes no `progress` arg)

- [ ] **Step 3: Implement** — replace the body of `run` in `src/startup_agent/services/ingestion.py`:

```python
    def run(self, progress=None) -> RunReport:
        companies = self._repo.get_companies()
        total = len(companies)
        report = RunReport(companies_count=total)
        had_failure = False

        for index, company in enumerate(companies, start=1):
            adapter = self._factory.for_company(company)
            if adapter is None:
                logger.info("skip_unsupported_ats", company=company.name,
                            ats_type=company.ats_type.value)
            else:
                try:
                    jobs = adapter.fetch_jobs(company)
                    report.jobs_fetched += len(jobs)
                    for job in jobs:
                        if self._repo.upsert_job(job):
                            report.jobs_new += 1
                except Exception as error:  # per-company isolation
                    had_failure = True
                    logger.warning("fetch_failed", company=company.name, error=str(error))

            if progress is not None:
                progress({
                    "done": index, "total": total, "company": company.name,
                    "jobs_fetched": report.jobs_fetched, "jobs_new": report.jobs_new,
                })

        report.status = "partial" if had_failure else "success"
        self._repo.record_run(report)
        return report
```

(Note the type hint omits `from __future__`; use `progress: "Callable[[dict], None] | None" = None` with `from collections.abc import Callable` imported at top if you prefer an explicit hint — keep it simple and untyped-default is fine.)

- [ ] **Step 4: Run tests to verify pass (incl. the no-callback path unchanged)**

Run: `uv run pytest tests/services/test_ingestion.py -v`
Expected: all PASS (existing tests that call `run()` with no args still pass)

- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/services/ingestion.py tests/services/test_ingestion.py
git commit -m "feat: optional progress callback on IngestionService (per-company)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Dependency providers + JobMatch schema + matching view

**Files:** Create `api/deps.py`, `api/schemas.py`, `api/matching_view.py`; Test `tests/api/test_matching_view.py`.

- [ ] **Step 1: Write the failing test** (`tests/api/test_matching_view.py`)

```python
from datetime import datetime, timezone

from startup_agent.domain.models import Job
from api.schemas import to_job_match


def test_to_job_match_shapes_fields():
    job = Job(company_id="c1", ats_job_id="1", title="Backend Engineer",
             url="https://x/1", location="Tel Aviv",
             posted_at=datetime.now(timezone.utc))
    m = to_job_match(job, 0.73, {"c1": "Acme"})
    assert m.title == "Backend Engineer"
    assert m.company == "Acme"
    assert m.location == "Tel Aviv"
    assert m.score == 73          # 0.73 -> 73
    assert m.url == "https://x/1"
    assert m.age_label.endswith("ago") or m.age_label == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_matching_view.py -v`
Expected: FAIL (`ModuleNotFoundError: api.schemas`)

- [ ] **Step 3: Implement** `api/schemas.py`:

```python
from datetime import datetime, timezone

from pydantic import BaseModel

from startup_agent.domain.models import Job


class JobMatch(BaseModel):
    title: str
    company: str
    location: str | None
    score: int
    url: str
    posted_at: str | None
    age_label: str


def _age_label(posted_at: datetime | None, now: datetime) -> str:
    if not posted_at:
        return ""
    delta = now - posted_at.astimezone(timezone.utc)
    if delta.days >= 1:
        return f"{delta.days}d ago"
    return f"{int(delta.seconds // 3600)}h ago"


def to_job_match(job: Job, score: float, company_names: dict[str, str],
                 now: datetime | None = None) -> JobMatch:
    now = now or datetime.now(timezone.utc)
    return JobMatch(
        title=job.title,
        company=company_names.get(job.company_id, "?"),
        location=job.location,
        score=int(score * 100),
        url=job.url,
        posted_at=job.posted_at.isoformat() if job.posted_at else None,
        age_label=_age_label(job.posted_at, now),
    )
```

`api/matching_view.py`:

```python
from startup_agent.config.preferences_loader import load_preferences
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository
from startup_agent.services.matching import SimilarityMatchingService

from api.schemas import JobMatch, to_job_match


def compute_matches(repo: JobRepository, embedder: Embedder,
                    preferences_path: str, threshold: float) -> list[JobMatch]:
    prefs = load_preferences(preferences_path)
    results = SimilarityMatchingService(
        repo=repo, embedder=embedder, preferences=prefs, threshold=threshold
    ).run()
    names = {c.id_hash: c.name for c in repo.get_companies()}
    return [to_job_match(job, score, names) for job, score in results]
```

`api/deps.py`:

```python
from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.config.settings import Settings
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository


def get_settings() -> Settings:
    return Settings()


def get_repo() -> JobRepository:
    repo = SQLiteJobRepository(get_settings().db_path)
    repo.init_schema()
    return repo


def get_embedder() -> Embedder:
    return LocalEmbedder(get_settings().embedding_model)


def get_factory() -> ATSAdapterFactory:
    return ATSAdapterFactory()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_matching_view.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/deps.py api/schemas.py api/matching_view.py tests/api/test_matching_view.py
git commit -m "feat: add JobMatch schema, matching view, DI providers" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: CV upload route (`POST /api/cv`)

**Files:** Create `api/routes/cv.py`; Modify `api/main.py` (mount router); Update `tests/api/conftest.py` (overrides); Test `tests/api/test_cv.py`.

- [ ] **Step 1: Expand `tests/api/conftest.py`** with overridable fakes + tmp db:

```python
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import deps
from startup_agent.config.settings import Settings


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "backend" in t.lower() else [0.0, 1.0] for t in texts]


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "web.db"),
                    preferences_path="data/preferences.yaml",
                    match_threshold=0.3)


@pytest.fixture
def client(settings):
    app.dependency_overrides[deps.get_settings] = lambda: settings
    app.dependency_overrides[deps.get_embedder] = lambda: FakeEmbedder()
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Write the failing test** (`tests/api/test_cv.py`) — uploads a blank PDF generated in-test:

```python
import io

from pypdf import PdfWriter


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_upload_cv_stores_and_returns_ready(client):
    files = {"file": ("cv.pdf", _blank_pdf_bytes(), "application/pdf")}
    resp = client.post("/api/cv", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert "chars" in body
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/api/test_cv.py -v`
Expected: FAIL (404 — route not mounted)

- [ ] **Step 4: Implement** `api/routes/cv.py`:

```python
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile

from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.cv.loader import read_pdf_text
from startup_agent.ports.embedder import Embedder

from api.deps import get_embedder, get_settings

router = APIRouter()


@router.post("/cv")
def upload_cv(file: UploadFile,
              embedder: Embedder = Depends(get_embedder),
              settings=Depends(get_settings)) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        text = read_pdf_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    vector = embedder.embed([text])[0]
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.save_cv(path=file.filename or "cv.pdf", text=text,
                 embedding=to_bytes(vector), model=settings.embedding_model)
    return {"status": "ready", "chars": len(text)}
```

Mount it in `api/main.py` — add import and `app.include_router(cv.router, prefix="/api")`:

```python
from api.routes import cv, health
...
app.include_router(health.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/api/test_cv.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add api/routes/cv.py api/main.py tests/api/conftest.py tests/api/test_cv.py
git commit -m "feat: add POST /api/cv (upload, parse, embed, store)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Run route with SSE progress (`GET /api/run`)

**Files:** Create `api/routes/run.py`; Modify `api/main.py`; Test `tests/api/test_run.py`.

- [ ] **Step 1: Write the failing test** (`tests/api/test_run.py`) — seeds companies via a fake factory, uploads a CV, then asserts the SSE stream ends with a `done` event:

```python
import io
import json

from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, AtsType


def _blank_pdf():
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    b = io.BytesIO(); w.write(b); return b.getvalue()


class _FakeAdapter:
    def fetch_jobs(self, company):
        cid = company.id_hash
        return [Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                    url="https://x/1", location="Tel Aviv", description="backend")]


class _FakeFactory:
    def for_company(self, company):
        return _FakeAdapter()


def _events(resp):
    for line in resp.iter_lines():
        if line and line.startswith("data: "):
            yield json.loads(line[len("data: "):])


def test_run_streams_progress_then_done(client, settings):
    # seed a company into the same tmp db the client uses
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    # upload CV
    client.post("/api/cv", files={"file": ("cv.pdf", _blank_pdf(), "application/pdf")})

    app.dependency_overrides[deps.get_factory] = lambda: _FakeFactory()
    with client.stream("GET", "/api/run") as resp:
        assert resp.status_code == 200
        stages = [ev["stage"] for ev in _events(resp)]
    assert "fetching" in stages
    assert stages[-1] == "done"


def test_run_without_cv_returns_400(client, settings):
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    app.dependency_overrides[deps.get_factory] = lambda: _FakeFactory()
    resp = client.get("/api/run")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_run.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement** `api/routes/run.py`:

```python
import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.services.ingestion import IngestionService

from api.deps import get_embedder, get_factory, get_settings
from api.matching_view import compute_matches

router = APIRouter()

_SENTINEL = object()


@router.get("/run")
def run(factory=Depends(get_factory), embedder=Depends(get_embedder),
        settings=Depends(get_settings)) -> StreamingResponse:
    # Fail fast if no CV — clean 400 instead of a mid-stream error.
    precheck = SQLiteJobRepository(settings.db_path)
    precheck.init_schema()
    if precheck.get_cv() is None:
        raise HTTPException(status_code=400, detail="No CV uploaded. Upload a CV first.")

    events: queue.Queue = queue.Queue()

    def worker():
        try:
            repo = SQLiteJobRepository(settings.db_path)  # own connection in this thread
            repo.init_schema()
            IngestionService(repo=repo, factory=factory).run(
                progress=lambda ev: events.put({"stage": "fetching", **ev})
            )
            matches = compute_matches(repo, embedder, settings.preferences_path,
                                      settings.match_threshold)
            events.put({"stage": "matching", "candidates": len(matches)})
            events.put({"stage": "done", "matched": len(matches),
                        "matches": [m.model_dump() for m in matches]})
        except Exception as error:  # noqa: BLE001 - surface any failure to the UI
            events.put({"stage": "error", "message": str(error)})
        finally:
            events.put(_SENTINEL)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            ev = events.get()
            if ev is _SENTINEL:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
```

Mount in `api/main.py`: add `run` to the import and `app.include_router(run.router, prefix="/api")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_run.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add api/routes/run.py api/main.py tests/api/test_run.py
git commit -m "feat: add GET /api/run (SSE fetch+match progress)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Results route (`GET /api/results`)

**Files:** Create `api/routes/results.py`; Modify `api/main.py`; Test `tests/api/test_results.py`.

- [ ] **Step 1: Write the failing test** (`tests/api/test_results.py`)

```python
import io

from pypdf import PdfWriter

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, AtsType


def _blank_pdf():
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    b = io.BytesIO(); w.write(b); return b.getvalue()


def test_results_returns_matches_shape(client, settings):
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    cid = repo.get_companies()[0].id_hash
    repo.upsert_job(Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                        url="https://x/1", location="Tel Aviv", description="backend"))
    client.post("/api/cv", files={"file": ("cv.pdf", _blank_pdf(), "application/pdf")})

    resp = client.get("/api/results")
    assert resp.status_code == 200
    body = resp.json()
    assert "matches" in body
    assert isinstance(body["matches"], list)
    if body["matches"]:
        m = body["matches"][0]
        assert {"title", "company", "location", "score", "url", "age_label"} <= m.keys()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_results.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement** `api/routes/results.py`:

```python
from fastapi import APIRouter, Depends

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository

from api.deps import get_embedder, get_settings
from api.matching_view import compute_matches

router = APIRouter()


@router.get("/results")
def results(embedder=Depends(get_embedder), settings=Depends(get_settings)) -> dict:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    if repo.get_cv() is None:
        return {"matches": []}
    matches = compute_matches(repo, embedder, settings.preferences_path,
                              settings.match_threshold)
    return {"matches": [m.model_dump() for m in matches]}
```

Mount in `api/main.py`.

- [ ] **Step 4: Run + full suite**

Run: `uv run pytest tests/api -v && uv run pytest -q`
Expected: api tests PASS; full suite green.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check api tests/api
git add api/routes/results.py api/main.py tests/api/test_results.py
git commit -m "feat: add GET /api/results (last ranked matches)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> **Backend checkpoint:** the full API works headless. Frontend tasks follow.

---

### Task 7: Frontend scaffold + API client + styles

**Files:** Create `frontend/` (Vite React-TS scaffold), `frontend/src/api/client.ts`, `frontend/src/styles/tokens.css`, `frontend/vite.config.ts`.

- [ ] **Step 1: Scaffold Vite + React + TS**

Run:
```bash
cd /Users/netanelsade/projects/startup-agent
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: Configure the dev proxy** — overwrite `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
```

- [ ] **Step 3: Design tokens** — `frontend/src/styles/tokens.css` (the Light-SaaS look):

```css
:root {
  --bg: #f7f8fa;
  --surface: #ffffff;
  --text: #1a1a2e;
  --muted: #6b7280;
  --accent: #4f46e5;
  --accent-soft: #eef2ff;
  --radius: 14px;
  --shadow: 0 2px 10px rgba(0,0,0,.06);
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font); }
```

- [ ] **Step 4: Typed API client** — `frontend/src/api/client.ts`:

```ts
export interface JobMatch {
  title: string;
  company: string;
  location: string | null;
  score: number;
  url: string;
  posted_at: string | null;
  age_label: string;
}

export type RunEvent =
  | { stage: "fetching"; done: number; total: number; company: string; jobs_fetched: number; jobs_new: number }
  | { stage: "matching"; candidates: number }
  | { stage: "done"; matched: number; matches: JobMatch[] }
  | { stage: "error"; message: string };

export async function uploadCv(file: File): Promise<{ status: string; chars: number }> {
  const body = new FormData();
  body.append("file", file);
  const resp = await fetch("/api/cv", { method: "POST", body });
  if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
  return resp.json();
}

// SSE via EventSource (GET). onEvent fires per progress event; resolves on done/error.
export function runStream(onEvent: (e: RunEvent) => void): EventSource {
  const es = new EventSource("/api/run");
  es.onmessage = (msg) => {
    const ev = JSON.parse(msg.data) as RunEvent;
    onEvent(ev);
    if (ev.stage === "done" || ev.stage === "error") es.close();
  };
  es.onerror = () => es.close();
  return es;
}
```

- [ ] **Step 5: Verify it builds**

Run: `cd /Users/netanelsade/projects/startup-agent/frontend && npm run build`
Expected: builds without type errors.

- [ ] **Step 6: Commit**

```bash
cd /Users/netanelsade/projects/startup-agent
echo "frontend/node_modules/" >> .gitignore
echo "frontend/dist/" >> .gitignore
git add frontend .gitignore
git commit -m "feat: scaffold React+Vite frontend (proxy, tokens, API client)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Frontend components + App states

**Files:** Create `frontend/src/components/{JobCard,JobList,CvUpload,RunProgress}.tsx`, `frontend/src/styles/app.css`; Replace `frontend/src/App.tsx`, `frontend/src/main.tsx`.

- [ ] **Step 1: `JobCard.tsx`**

```tsx
import type { JobMatch } from "../api/client";

export function JobCard({ job }: { job: JobMatch }) {
  return (
    <div className="card">
      <div className="card-top">
        <b>{job.title}</b>
        <span className="score">{job.score}</span>
      </div>
      <div className="muted">
        {job.company}{job.location ? ` · ${job.location}` : ""}{job.age_label ? ` · ${job.age_label}` : ""}
      </div>
      <a className="apply" href={job.url} target="_blank" rel="noreferrer">Apply →</a>
    </div>
  );
}
```

- [ ] **Step 2: `JobList.tsx`**

```tsx
import type { JobMatch } from "../api/client";
import { JobCard } from "./JobCard";

export function JobList({ jobs }: { jobs: JobMatch[] }) {
  if (!jobs.length) return <p className="muted">No matching jobs.</p>;
  return <div className="job-list">{jobs.map((j, i) => <JobCard key={i} job={j} />)}</div>;
}
```

- [ ] **Step 3: `CvUpload.tsx`**

```tsx
import { useState } from "react";
import { uploadCv } from "../api/client";

export function CvUpload({ onReady }: { onReady: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle(file: File) {
    setBusy(true); setError(null);
    try { await uploadCv(file); onReady(); }
    catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="card upload">
      <h3>Upload your CV (PDF)</h3>
      <input type="file" accept="application/pdf" disabled={busy}
             onChange={(e) => e.target.files?.[0] && handle(e.target.files[0])} />
      {busy && <p className="muted">Reading & embedding…</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: `RunProgress.tsx`**

```tsx
import type { RunEvent } from "../api/client";

export function RunProgress({ last }: { last: RunEvent | null }) {
  if (!last) return <p className="muted">Starting…</p>;
  if (last.stage === "fetching") {
    const pct = Math.round((last.done / last.total) * 100);
    return (
      <div className="progress">
        <div className="bar"><div className="fill" style={{ width: `${pct}%` }} /></div>
        <p className="muted">Fetching {last.done}/{last.total} — {last.company} · {last.jobs_fetched} jobs</p>
      </div>
    );
  }
  if (last.stage === "matching") return <p className="muted">Matching {last.candidates} candidates…</p>;
  if (last.stage === "error") return <p className="error">Error: {last.message}</p>;
  return <p className="muted">Done.</p>;
}
```

- [ ] **Step 5: `App.tsx`** — the three states:

```tsx
import { useState } from "react";
import "./styles/tokens.css";
import "./styles/app.css";
import { CvUpload } from "./components/CvUpload";
import { RunProgress } from "./components/RunProgress";
import { JobList } from "./components/JobList";
import { runStream, type RunEvent, type JobMatch } from "./api/client";

type Phase = "upload" | "running" | "results";

export default function App() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [last, setLast] = useState<RunEvent | null>(null);
  const [jobs, setJobs] = useState<JobMatch[]>([]);

  function start() {
    setPhase("running"); setLast(null);
    runStream((ev) => {
      setLast(ev);
      if (ev.stage === "done") { setJobs(ev.matches); setPhase("results"); }
    });
  }

  const summary = phase === "results" ? `${jobs.length} matches` : "";

  return (
    <div className="app">
      <header className="header">
        <span className="brand">JobScout</span>
        <span className="muted">{summary}</span>
      </header>
      <main className="main">
        {phase === "upload" && <CvUpload onReady={start} />}
        {phase === "running" && <RunProgress last={last} />}
        {phase === "results" && <JobList jobs={jobs} />}
      </main>
    </div>
  );
}
```

- [ ] **Step 6: `main.tsx`** (ensure it renders `App` cleanly):

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode><App /></StrictMode>
);
```

- [ ] **Step 7: `styles/app.css`** (Light-SaaS polish):

```css
.app { max-width: 760px; margin: 0 auto; padding: 24px 16px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.brand { font-weight: 800; color: var(--accent); font-size: 20px; }
.muted { color: var(--muted); font-size: 14px; }
.error { color: #b91c1c; font-size: 14px; }
.card { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow); padding: 16px; margin-bottom: 12px; }
.card-top { display: flex; justify-content: space-between; align-items: center; }
.score { background: var(--accent-soft); color: var(--accent); border-radius: 20px; padding: 2px 10px; font-weight: 700; font-size: 13px; }
.apply { display: inline-block; margin-top: 10px; background: var(--accent); color: #fff; text-decoration: none; border-radius: 8px; padding: 6px 14px; font-size: 13px; }
.upload h3 { margin-top: 0; }
.progress .bar { background: #e5e7eb; border-radius: 8px; height: 10px; overflow: hidden; }
.progress .fill { background: var(--accent); height: 100%; transition: width .2s; }
.job-list { display: flex; flex-direction: column; }
```

- [ ] **Step 8: Verify build**

Run: `cd /Users/netanelsade/projects/startup-agent/frontend && npm run build`
Expected: builds clean.

- [ ] **Step 9: Commit**

```bash
cd /Users/netanelsade/projects/startup-agent
git add frontend/src
git commit -m "feat: frontend components + 3-state App (upload/run/results)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: One-command dev runner + live smoke + checkpoint

**Files:** Create `Makefile`.

- [ ] **Step 1: `Makefile`**

```make
.PHONY: dev backend frontend
backend:
	uv run uvicorn api.main:app --reload --port 8000
frontend:
	cd frontend && npm run dev
dev:
	uv run uvicorn api.main:app --port 8000 & cd frontend && npm run dev
```

- [ ] **Step 2: Live smoke (manual)** — start backend, ensure DB has companies + jobs:

```bash
cd /Users/netanelsade/projects/startup-agent
uv run startup-agent refresh-companies
uv run startup-agent run            # populate jobs (a few min)
make dev                            # then open http://localhost:5173
```
Open the browser: upload `~/Downloads/Netanel_Sade.pdf`, watch the progress bar fill as companies are fetched, then see ranked job cards with Apply links.

- [ ] **Step 3: Full backend suite green**

Run: `uv run pytest -q && uv run ruff check api tests`
Expected: all green.

- [ ] **Step 4: Commit + merge to main**

```bash
git add Makefile
git commit -m "feat: add make dev runner for the local web app" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> **Checkpoint:** the local web app runs end-to-end. Merge `phase-6/local-web` → `main`.

---

## Self-Review Notes

- **Spec coverage:** 3-layer architecture (Tasks 1,3,7); API contract — health (1), cv (4), run/SSE (5), results (6); JobMatch shape (3); SSE event shapes (5); data flow upload→run→results (4,5,8); engine progress callback, additive (2); error handling — no-CV 400 (5), error SSE event (5), CORS (1); Light-SaaS visual (7,8); testing via TestClient + fakes (3-6) and engine callback test (2); `make dev` (9). All spec sections map to tasks.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `JobMatch` fields (title/company/location/score/url/posted_at/age_label) identical across `schemas.py`, `client.ts`, tests, and `JobCard`. `RunEvent` stages (fetching/matching/done/error) consistent across `run.py`, `client.ts`, `RunProgress`. `IngestionService.run(progress=...)` signature consistent (Task 2 ↔ Task 5). `compute_matches(repo, embedder, preferences_path, threshold)` consistent (Tasks 3,5,6). DI providers `get_settings/get_repo/get_embedder/get_factory` consistent across deps + routes + conftest overrides.
- **Note:** `/api/results` and `/api/run` recompute matches from the DB (embeddings cached, so cheap) rather than sharing mutable server state — simpler and stateless. Acceptable per spec's single-user scope.
