# Phase 0 + Phase 1 Implementation Plan — Spike & Skeleton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the ATS-adapter approach against real Israeli startups (Phase 0), then build the clean hexagonal skeleton — domain models, port interfaces, SQLite repository, config, CLI — that every later phase plugs into (Phase 1).

**Architecture:** Ports & adapters (hexagonal). `domain/` holds pure typed models; `ports/` holds abstract interfaces; `adapters/` holds concrete implementations; `services/` orchestrates; `factories/` wires by config. Phase 1 ships the backbone + the storage adapter only; ATS/embedding/ranking adapters arrive in later phases against their interfaces.

**Tech Stack:** Python 3.13, `uv` (env + deps), `pydantic` v2 (domain models + settings), `sqlite3` (stdlib), `pytest` (+ `pytest-cov`), `ruff` (lint/format), `httpx` (Phase 0 fetching), `structlog` (logging). LLM/embeddings deferred to Phase 3.

**Workflow:** One branch per task (`phase-N/slug`), `test:`→`feat:` commits, merge to `main` only when its tests pass. `main` is always the last known-good checkpoint.

---

## File Structure (Phase 1 target)

```
pyproject.toml                      packaging, deps, tool config (ruff/pytest)
src/startup_agent/
  __init__.py
  domain/
    __init__.py
    models.py                       Company, RawJob, Job, MatchResult, RunReport, AtsType (enum)
    preferences.py                  Preferences model
  ports/
    __init__.py
    repository.py                   JobRepository (ABC)
    ats.py                          ATSAdapter (Protocol/ABC) — defined now, implemented Phase 2
    embedder.py                     Embedder (ABC) — defined now, implemented Phase 3
    ranker.py                       Ranker (ABC) — defined now, implemented Phase 3
    delivery.py                     DeliveryChannel (ABC) — defined now, implemented Phase 4
  adapters/
    __init__.py
    storage/
      __init__.py
      schema.sql                    DDL for companies/jobs/cv/runs/matches
      sqlite_repository.py          SQLiteJobRepository(JobRepository)
  config/
    __init__.py
    settings.py                     Settings (pydantic-settings) + loader
  logging.py                        structlog setup
  cli.py                            Typer app: init-db, version
tests/
  conftest.py                       in-memory repo fixture
  domain/test_models.py
  adapters/storage/test_sqlite_repository.py
  config/test_settings.py
docs/
  specs/2026-06-12-startup-job-agent-design.md   (already written)
  plans/2026-06-12-phase-0-1-spike-and-skeleton.md (this file)
spike/                              Phase 0 outputs (scripts + fixtures + report)
  fixtures/                         recorded real ATS JSON
  report.md                         coverage findings
```

---

# PHASE 0 — Discovery Spike

> Phase 0 is exploratory: its purpose is to learn how SNC and the ATSes actually
> behave, and to capture real fixtures for Phase 2 tests. It is NOT TDD — it is
> investigation with concrete, checkable deliverables. Work on branch
> `phase-0/discovery-spike`; merge to main when the report + fixtures exist.

### Task 0.1: Project bootstrap for the spike

**Files:**
- Create: `pyproject.toml`, `src/startup_agent/__init__.py`, `spike/.gitkeep`, `.gitignore`

- [ ] **Step 1: Init env and packaging**

```bash
cd ~/projects/startup-agent
uv init --package --name startup-agent --python 3.13 . 2>/dev/null || true
uv add httpx pydantic pydantic-settings structlog typer
uv add --dev pytest pytest-cov ruff
```

- [ ] **Step 2: Add `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
jobs.db
.env
spike/fixtures/*.json
!spike/fixtures/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: bootstrap project (uv, deps, gitignore)"
```

### Task 0.2: Determine how to obtain the SNC company list

**Files:** Create `spike/explore_snc.py`

- [ ] **Step 1:** Write a script that probes Startup Nation Central's Finder
  (`finder.startupnationcentral.org`) to determine the data access path:
  inspect network calls (does the site call a JSON API?), check for a public
  endpoint, and if found fetch one page of companies and print fields available
  (name, website, sector, size). If no API, document that scraping is required
  and capture the HTML structure of one results page.
- [ ] **Step 2:** Run it; record findings (API URL + params, or "scrape needed")
  into `spike/report.md` under "## SNC access".
- [ ] **Step 3:** Save a sample of ~50 companies (name + website) to
  `spike/fixtures/snc_sample.json`.
- [ ] **Step 4:** Commit `git add spike && git commit -m "spike: document SNC company-list access"`.

### Task 0.3: ATS detection on the sample

**Files:** Create `spike/detect_ats.py`

- [ ] **Step 1:** For each of the ~50 sampled companies, fetch the homepage,
  follow the careers link, and classify the ATS by URL/markers:
  `comeet.com`/`comeet.co` → comeet; `boards.greenhouse.io`/`greenhouse.io` →
  greenhouse; `jobs.lever.co` → lever; `apply.workable.com` → workable;
  `jobs.ashbyhq.com` → ashby; `careers.smartrecruiters.com` → smartrecruiters;
  else → unknown. Extract the board token from the URL.
- [ ] **Step 2:** Run it; write a coverage table to `spike/report.md`
  ("## ATS coverage": counts + % per ATS, list of unknowns).
- [ ] **Step 3:** Commit `git add spike && git commit -m "spike: ATS detection + coverage table"`.

### Task 0.4: Capture real ATS job payloads (fixtures)

**Files:** Create `spike/fetch_jobs.py`

- [ ] **Step 1:** For 2–3 companies on each detected ATS, hit that ATS's public
  jobs JSON endpoint and save the raw response to
  `spike/fixtures/<ats>_<company>.json`. Probe these documented endpoints and
  record which work:
  - Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
  - Lever: `https://api.lever.co/v0/postings/{token}?mode=json`
  - Comeet: company careers JSON (confirm exact endpoint during spike)
  - Workable: `https://apply.workable.com/api/v3/accounts/{token}/jobs`
  - Ashby: `https://api.ashbyhq.com/posting-api/job-board/{token}`
  - SmartRecruiters: `https://api.smartrecruiters.com/v1/companies/{token}/postings`
- [ ] **Step 2:** For each working ATS, note in `spike/report.md` the field map
  needed for normalization: where to find job id, title, location, url,
  description, posted/updated date.
- [ ] **Step 3:** Commit `git add spike && git commit -m "spike: capture real ATS job fixtures + field maps"`.

### Task 0.5: Spike decision report

**Files:** Modify `spike/report.md`

- [ ] **Step 1:** Add a "## Decision" section: overall ATS coverage %, which
  adapters to build first (by coverage), confirmed endpoints + field maps,
  SNC access method, and any blockers. This report drives the Phase 2 plan.
- [ ] **Step 2:** Commit, push branch, open PR, merge to `main`.

```bash
git add spike && git commit -m "spike: phase-0 decision report"
git push -u origin phase-0/discovery-spike
```

> **Checkpoint:** `main` now contains validated approach + real fixtures. STOP and
> review the report with the user before writing the Phase 2 plan.

---

# PHASE 1 — Skeleton & Foundations

> Fully TDD. Branch per task. No external unknowns here — all internal.

### Task 1.1: Domain models

**Files:**
- Create: `src/startup_agent/domain/models.py`
- Test: `tests/domain/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_models.py
from startup_agent.domain.models import Company, Job, AtsType


def test_company_requires_name_and_defaults_active():
    c = Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme")
    assert c.name == "Acme"
    assert c.ats_type is AtsType.GREENHOUSE
    assert c.active is True


def test_job_id_is_stable_hash_of_company_and_ats_job_id():
    j1 = Job(company_id="c1", ats_job_id="42", title="Backend Engineer",
             url="https://x/42", location="Tel Aviv")
    j2 = Job(company_id="c1", ats_job_id="42", title="changed later",
             url="https://x/42", location="Tel Aviv")
    assert j1.id == j2.id  # id derives only from company_id + ats_job_id


def test_unknown_ats_type_is_supported():
    assert AtsType("unknown") is AtsType.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: startup_agent.domain.models`

- [ ] **Step 3: Write minimal implementation**

```python
# src/startup_agent/domain/models.py
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class AtsType(str, Enum):
    COMEET = "comeet"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKABLE = "workable"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"
    UNKNOWN = "unknown"


class Company(BaseModel):
    name: str
    website: str | None = None
    careers_url: str | None = None
    ats_type: AtsType = AtsType.UNKNOWN
    ats_token: str | None = None
    sector: str | None = None
    size: str | None = None
    source: str = "snc"
    active: bool = True


class RawJob(BaseModel):
    """Provider-shaped job as returned by an ATS, pre-normalization."""
    ats_job_id: str
    payload: dict


class Job(BaseModel):
    company_id: str
    ats_job_id: str
    title: str
    url: str
    location: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    first_seen_at: datetime | None = None

    @computed_field
    @property
    def id(self) -> str:
        raw = f"{self.company_id}:{self.ats_job_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MatchResult(BaseModel):
    job_id: str
    score: int = Field(ge=0, le=100)
    reason: str
    stage: str


class RunReport(BaseModel):
    companies_count: int = 0
    jobs_fetched: int = 0
    jobs_new: int = 0
    jobs_matched: int = 0
    status: str = "success"
    error: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/domain tests/domain
git commit -m "feat: add domain models (Company, Job, MatchResult, RunReport)"
```

### Task 1.2: Preferences model

**Files:**
- Create: `src/startup_agent/domain/preferences.py`
- Test: `tests/domain/test_preferences.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/test_preferences.py
from startup_agent.domain.preferences import Preferences


def test_preferences_defaults_and_parsing():
    p = Preferences(
        roles=["backend", "ai"],
        seniority=["mid", "senior"],
        locations=["Tel Aviv", "Remote"],
        must_have=["python"],
        exclude=["unpaid"],
    )
    assert "backend" in p.roles
    assert p.exclude == ["unpaid"]


def test_preferences_empty_is_valid():
    p = Preferences()
    assert p.roles == []
    assert p.locations == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_preferences.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/startup_agent/domain/preferences.py
from __future__ import annotations

from pydantic import BaseModel, Field


class Preferences(BaseModel):
    roles: list[str] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_preferences.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/domain/preferences.py tests/domain/test_preferences.py
git commit -m "feat: add Preferences model"
```

### Task 1.3: Port interfaces (contracts)

**Files:**
- Create: `src/startup_agent/ports/repository.py`, `ports/ats.py`, `ports/embedder.py`, `ports/ranker.py`, `ports/delivery.py`, `ports/__init__.py`
- Test: `tests/ports/test_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ports/test_contracts.py
import inspect

from startup_agent.ports.repository import JobRepository
from startup_agent.ports.ats import ATSAdapter
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.ranker import Ranker
from startup_agent.ports.delivery import DeliveryChannel


def test_repository_is_abstract_with_required_methods():
    assert inspect.isabstract(JobRepository)
    for m in ("upsert_company", "get_companies", "upsert_job",
              "job_exists", "record_run", "record_matches"):
        assert hasattr(JobRepository, m)


def test_other_ports_are_abstract():
    for port in (ATSAdapter, Embedder, Ranker, DeliveryChannel):
        assert inspect.isabstract(port)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ports/test_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementations**

```python
# src/startup_agent/ports/repository.py
from __future__ import annotations

from abc import ABC, abstractmethod

from startup_agent.domain.models import Company, Job, MatchResult, RunReport


class JobRepository(ABC):
    @abstractmethod
    def upsert_company(self, company: Company) -> str: ...

    @abstractmethod
    def get_companies(self, active_only: bool = True) -> list[Company]: ...

    @abstractmethod
    def upsert_job(self, job: Job) -> bool:
        """Returns True if the job is new (was not previously seen)."""

    @abstractmethod
    def job_exists(self, job_id: str) -> bool: ...

    @abstractmethod
    def record_run(self, report: RunReport) -> int: ...

    @abstractmethod
    def record_matches(self, run_id: int, matches: list[MatchResult]) -> None: ...
```

```python
# src/startup_agent/ports/ats.py
from __future__ import annotations

from abc import ABC, abstractmethod

from startup_agent.domain.models import AtsType, Company, RawJob


class ATSAdapter(ABC):
    ats_type: AtsType

    @abstractmethod
    def fetch_jobs(self, company: Company) -> list[RawJob]: ...
```

```python
# src/startup_agent/ports/embedder.py
from __future__ import annotations

from abc import ABC, abstractmethod


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

```python
# src/startup_agent/ports/ranker.py
from __future__ import annotations

from abc import ABC, abstractmethod

from startup_agent.domain.models import Job, MatchResult


class Ranker(ABC):
    @abstractmethod
    def rank(self, cv_text: str, jobs: list[Job]) -> list[MatchResult]: ...
```

```python
# src/startup_agent/ports/delivery.py
from __future__ import annotations

from abc import ABC, abstractmethod


class DeliveryChannel(ABC):
    @abstractmethod
    def deliver(self, title: str, body: str) -> None: ...
```

```python
# src/startup_agent/ports/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ports/test_contracts.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/ports tests/ports
git commit -m "feat: define port interfaces (repository, ats, embedder, ranker, delivery)"
```

### Task 1.4: SQLite schema

**Files:**
- Create: `src/startup_agent/adapters/storage/schema.sql`

- [ ] **Step 1: Write the schema**

```sql
-- src/startup_agent/adapters/storage/schema.sql
CREATE TABLE IF NOT EXISTS companies (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    website      TEXT,
    careers_url  TEXT,
    ats_type     TEXT NOT NULL DEFAULT 'unknown',
    ats_token    TEXT,
    sector       TEXT,
    size         TEXT,
    source       TEXT NOT NULL DEFAULT 'snc',
    active       INTEGER NOT NULL DEFAULT 1,
    added_at     TEXT NOT NULL,
    last_fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    company_id    TEXT NOT NULL REFERENCES companies(id),
    ats_job_id    TEXT NOT NULL,
    title         TEXT NOT NULL,
    location      TEXT,
    url           TEXT NOT NULL,
    description   TEXT,
    posted_at     TEXT,
    first_seen_at TEXT NOT NULL,
    embedding     BLOB,
    raw_json      TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at);

CREATE TABLE IF NOT EXISTS cv (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    path       TEXT NOT NULL,
    text       TEXT NOT NULL,
    embedding  BLOB,
    model      TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    companies_count INTEGER NOT NULL DEFAULT 0,
    jobs_fetched    INTEGER NOT NULL DEFAULT 0,
    jobs_new        INTEGER NOT NULL DEFAULT 0,
    jobs_matched    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    error           TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    score      INTEGER NOT NULL,
    reason     TEXT,
    stage      TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_matches_run ON matches(run_id);
```

- [ ] **Step 2: Commit**

```bash
git add src/startup_agent/adapters/storage/schema.sql
git commit -m "feat: add SQLite schema (companies, jobs, cv, runs, matches)"
```

### Task 1.5: SQLiteJobRepository

**Files:**
- Create: `src/startup_agent/adapters/storage/sqlite_repository.py`, `adapters/__init__.py`, `adapters/storage/__init__.py`
- Test: `tests/adapters/storage/test_sqlite_repository.py`, `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/conftest.py
import pytest

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository


@pytest.fixture
def repo():
    # ":memory:" gives a fresh in-memory DB per test
    r = SQLiteJobRepository(":memory:")
    r.init_schema()
    return r
```

```python
# tests/adapters/storage/test_sqlite_repository.py
from startup_agent.domain.models import Company, Job, AtsType, RunReport, MatchResult


def test_upsert_and_get_company(repo):
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.LEVER, ats_token="acme"))
    companies = repo.get_companies()
    assert len(companies) == 1
    assert companies[0].name == "Acme"


def test_upsert_job_returns_true_only_first_time(repo):
    repo.upsert_company(Company(name="Acme"))
    company_id = repo.get_companies()[0].id_hash  # see note in impl
    job = Job(company_id=company_id, ats_job_id="1", title="Backend", url="https://x/1")
    assert repo.upsert_job(job) is True   # new
    assert repo.upsert_job(job) is False  # already seen -> dedup
    assert repo.job_exists(job.id) is True


def test_record_run_and_matches(repo):
    run_id = repo.record_run(RunReport(companies_count=3, jobs_fetched=10, jobs_new=4))
    assert isinstance(run_id, int)
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job = Job(company_id=cid, ats_job_id="1", title="Backend", url="https://x/1")
    repo.upsert_job(job)
    repo.record_matches(run_id, [MatchResult(job_id=job.id, score=88, reason="fit", stage="llm")])
    # no exception == pass; deeper assertions added when query methods exist
```

> **Note for implementer:** `Company` has no stored id until persisted. Give the
> repository the job of assigning `companies.id` = `sha256(name)[:16]` and expose
> it. To keep the test above working, add a helper `id_hash` on `Company` mirroring
> that rule (pure function, no DB). Add this to `domain/models.py` Company:
> ```python
> @computed_field
> @property
> def id_hash(self) -> str:
>     return hashlib.sha256(self.name.encode()).hexdigest()[:16]
> ```
> (Add a one-line test for it in `tests/domain/test_models.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/adapters/storage/test_sqlite_repository.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/startup_agent/adapters/storage/sqlite_repository.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from importlib import resources

from startup_agent.domain.models import (
    AtsType, Company, Job, MatchResult, RunReport,
)
from startup_agent.ports.repository import JobRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteJobRepository(JobRepository):
    def __init__(self, db_path: str = "jobs.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        ddl = (
            resources.files("startup_agent.adapters.storage")
            .joinpath("schema.sql")
            .read_text()
        )
        self._conn.executescript(ddl)
        self._conn.commit()

    def upsert_company(self, company: Company) -> str:
        cid = company.id_hash
        self._conn.execute(
            """INSERT INTO companies
               (id,name,website,careers_url,ats_type,ats_token,sector,size,source,active,added_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 website=excluded.website, careers_url=excluded.careers_url,
                 ats_type=excluded.ats_type, ats_token=excluded.ats_token,
                 sector=excluded.sector, size=excluded.size, active=excluded.active""",
            (cid, company.name, company.website, company.careers_url,
             company.ats_type.value, company.ats_token, company.sector,
             company.size, company.source, int(company.active), _now()),
        )
        self._conn.commit()
        return cid

    def get_companies(self, active_only: bool = True) -> list[Company]:
        q = "SELECT * FROM companies"
        if active_only:
            q += " WHERE active = 1"
        rows = self._conn.execute(q).fetchall()
        return [
            Company(
                name=r["name"], website=r["website"], careers_url=r["careers_url"],
                ats_type=AtsType(r["ats_type"]), ats_token=r["ats_token"],
                sector=r["sector"], size=r["size"], source=r["source"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    def upsert_job(self, job: Job) -> bool:
        if self.job_exists(job.id):
            return False
        self._conn.execute(
            """INSERT INTO jobs
               (id,company_id,ats_job_id,title,location,url,description,posted_at,first_seen_at,raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (job.id, job.company_id, job.ats_job_id, job.title, job.location,
             job.url, job.description,
             job.posted_at.isoformat() if job.posted_at else None,
             _now(), json.dumps({})),
        )
        self._conn.commit()
        return True

    def job_exists(self, job_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def record_run(self, report: RunReport) -> int:
        cur = self._conn.execute(
            """INSERT INTO runs
               (started_at,finished_at,companies_count,jobs_fetched,jobs_new,jobs_matched,status,error)
               VALUES (?,?,?,?,?,?,?,?)""",
            (_now(), _now(), report.companies_count, report.jobs_fetched,
             report.jobs_new, report.jobs_matched, report.status, report.error),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def record_matches(self, run_id: int, matches: list[MatchResult]) -> None:
        self._conn.executemany(
            """INSERT INTO matches (run_id,job_id,score,reason,stage,created_at)
               VALUES (?,?,?,?,?,?)""",
            [(run_id, m.job_id, m.score, m.reason, m.stage, _now()) for m in matches],
        )
        self._conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/adapters/storage/ -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/adapters tests/adapters tests/conftest.py
git commit -m "feat: add SQLiteJobRepository with dedup + run/match recording"
```

### Task 1.6: Typed settings

**Files:**
- Create: `src/startup_agent/config/settings.py`, `config/__init__.py`
- Test: `tests/config/test_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_settings.py
from startup_agent.config.settings import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    s = Settings()
    assert s.db_path == "jobs.db"
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.shortlist_size == 20


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setenv("SHORTLIST_SIZE", "5")
    s = Settings()
    assert s.db_path == "/tmp/custom.db"
    assert s.shortlist_size == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/startup_agent/config/settings.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "jobs.db"
    cv_path: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    shortlist_size: int = 20
    anthropic_api_key: str = ""
    digest_dir: str = "digests"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_settings.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/config tests/config
git commit -m "feat: add typed Settings (pydantic-settings)"
```

### Task 1.7: Logging + CLI scaffold (`init-db`)

**Files:**
- Create: `src/startup_agent/logging.py`, `src/startup_agent/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner

from startup_agent.cli import app

runner = CliRunner()


def test_init_db_creates_schema(tmp_path):
    db = tmp_path / "t.db"
    result = runner.invoke(app, ["init-db", "--db-path", str(db)])
    assert result.exit_code == 0
    assert db.exists()
    assert "initialized" in result.stdout.lower()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/startup_agent/logging.py
from __future__ import annotations

import logging

import structlog


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )
```

```python
# src/startup_agent/cli.py
from __future__ import annotations

import typer

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository

app = typer.Typer(help="Israeli startup job agent")


@app.command("init-db")
def init_db(db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Create the SQLite schema."""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    typer.echo(f"Database initialized at {db_path}")


@app.command("version")
def version() -> None:
    typer.echo("startup-agent 0.1.0")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Full suite + lint, then commit**

```bash
uv run pytest -q && uv run ruff check src tests
git add src/startup_agent/cli.py src/startup_agent/logging.py tests/test_cli.py
git commit -m "feat: add logging + CLI scaffold (init-db, version)"
```

### Task 1.8: Phase-1 checkpoint

- [ ] **Step 1:** Confirm full suite green + coverage printed:
  `uv run pytest --cov=startup_agent -q`
- [ ] **Step 2:** Manual smoke: `uv run startup-agent init-db --db-path /tmp/smoke.db` and inspect with `sqlite3 /tmp/smoke.db ".tables"` (expect: companies cv jobs matches runs).
- [ ] **Step 3:** Push branch(es), open PR, merge to `main`.

> **Checkpoint:** `main` now has a tested skeleton: domain, ports, SQLite storage,
> config, CLI. Everything later plugs into these interfaces. STOP — the Phase 2
> plan (ATS adapters + factory + ingestion) is written next, using the real
> fixtures captured in Phase 0.

---

## Self-Review Notes

- **Spec coverage:** Phase 0 covers §2/§3 validation + fixtures; Phase 1 covers
  §5 architecture backbone, §6 data model, §10 config. Ports for embedder/
  ranker/delivery/ats are defined here (interfaces) and implemented in their
  phases (§7/§8). Matching (§7), digest (§8), scheduling (§13 Phase 5) are
  explicitly deferred to their own plans — by design, after Phase 0.
- **Placeholder scan:** none — every code/test step is concrete.
- **Type consistency:** `AtsType` enum, `Job.id` (sha256[:16] of company:ats_job_id),
  `Company.id_hash` (sha256[:16] of name), `JobRepository` method names, and
  `Settings` fields are used consistently across tasks.
