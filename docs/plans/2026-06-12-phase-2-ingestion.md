# Phase 2 Implementation Plan — Ingestion (fetch real jobs into the DB)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `startup-agent run` loads the company list, fetches current job postings from each company's ATS (Greenhouse + Ashby), normalizes them into our `Job` model, and stores only *new* ones (dedup). Re-running the same day adds zero duplicates.

**Architecture:** Builds on the Phase 1 skeleton. ATS adapters (one class per platform) implement the `ATSAdapter` port and are produced by a registry-backed `ATSAdapterFactory`. Each adapter fetches via an injectable JSON fetcher (so tests run offline against the Phase 0 fixtures) and maps the provider payload into our `Job` model. An `IngestionService` orchestrates: load companies → pick adapter per company → fetch → dedup-store → record a run, with per-company error isolation.

**Tech Stack:** Python 3.13+, httpx (HTTP + `MockTransport` for tests), pydantic v2, pytest. Real ATS fixtures live in `spike/fixtures/`.

**Workflow:** Branch `phase-2/ingestion`. TDD per task (`test:`→`feat:`), merge to `main` at the checkpoint when all tests pass.

---

## Decisions locked for this phase

- **Adapters return `list[Job]` (normalized), not `RawJob`.** Each ATS has a different shape, so the adapter is the natural place to own its mapping (cohesive, testable). We update the `ATSAdapter` port signature accordingly (it was provisional in Phase 1).
- **Company source for v1 = curated known-set** at `data/companies.json` (name, website, ats_type, ats_token) built from the spike's verified companies. The 247-name `companies_seed.json` and auto-token-discovery are a later phase.
- **Description text:** Greenhouse `content` is HTML-entity-encoded → store `html.unescape(content)`. Ashby → store `descriptionPlain`.
- **`ats_job_id` is always a string** (Greenhouse ids are ints → `str(id)`; Ashby ids are UUID strings).
- **Offline tests:** adapters take a `fetch_json: Callable[[str], dict]` in their constructor; tests inject a stub returning fixture JSON. No network in the test suite.

## File Structure (new in Phase 2)

```
data/companies.json                              curated known companies (name, website, ats_type, ats_token)
src/startup_agent/adapters/ats/
  __init__.py
  http_fetcher.py        HttpJsonFetcher — httpx GET w/ retry/backoff/timeout (the default fetch_json)
  greenhouse.py          GreenhouseAdapter(ATSAdapter)
  ashby.py               AshbyAdapter(ATSAdapter)
src/startup_agent/factories/
  __init__.py
  ats_factory.py         ATSAdapterFactory (registry: AtsType -> adapter)
src/startup_agent/companies/
  __init__.py
  ats_detection.py       detect_ats(url) -> (AtsType, token|None)   [utility, used for careers URLs]
  loader.py              load_companies_from_seed(path) -> list[Company]
src/startup_agent/services/
  __init__.py
  ingestion.py           IngestionService.run() -> RunReport
tests/adapters/ats/{test_http_fetcher,test_greenhouse,test_ashby}.py
tests/factories/test_ats_factory.py
tests/companies/{test_ats_detection,test_loader}.py
tests/services/test_ingestion.py
```

---

### Task 2.1: Update the `ATSAdapter` port to return `Job`

**Files:** Modify `src/startup_agent/ports/ats.py`; Modify `tests/ports/test_contracts.py`

- [ ] **Step 1: Update the contract test** — add an assertion that `ATSAdapter.fetch_jobs` exists and the port is abstract (already there). Add:

```python
def test_ats_adapter_has_fetch_jobs():
    assert hasattr(ATSAdapter, "fetch_jobs")
```

- [ ] **Step 2: Change the port** (`src/startup_agent/ports/ats.py`):

```python
from abc import ABC, abstractmethod

from startup_agent.domain.models import AtsType, Company, Job


class ATSAdapter(ABC):
    ats_type: AtsType

    @abstractmethod
    def fetch_jobs(self, company: Company) -> list[Job]: ...
```

- [ ] **Step 3: Run** `uv run pytest tests/ports -v` → PASS.
- [ ] **Step 4: Commit**

```bash
git add src/startup_agent/ports/ats.py tests/ports/test_contracts.py
git commit -m "refactor: ATSAdapter.fetch_jobs returns normalized list[Job]" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.2: HttpJsonFetcher (real HTTP with retry)

**Files:** Create `src/startup_agent/adapters/ats/__init__.py` (empty), `src/startup_agent/adapters/ats/http_fetcher.py`; Test `tests/adapters/ats/__init__.py` (empty), `tests/adapters/ats/test_http_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
import httpx

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher


def test_fetcher_returns_parsed_json():
    def handler(request):
        return httpx.Response(200, json={"ok": True})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch = HttpJsonFetcher(client=client, backoff=0.0)
    assert fetch("https://example.test/api")["ok"] is True


def test_fetcher_retries_then_succeeds():
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch = HttpJsonFetcher(client=client, retries=3, backoff=0.0)
    assert fetch("https://example.test/api")["ok"] is True
    assert calls["n"] == 3


def test_fetcher_raises_after_exhausting_retries():
    def handler(request):
        return httpx.Response(503)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch = HttpJsonFetcher(client=client, retries=2, backoff=0.0)
    import pytest
    with pytest.raises(httpx.HTTPError):
        fetch("https://example.test/api")
```

- [ ] **Step 2: Run** → FAIL (ModuleNotFoundError).
- [ ] **Step 3: Implement** (`src/startup_agent/adapters/ats/http_fetcher.py`)

```python
import time
from collections.abc import Callable

import httpx

JsonFetcher = Callable[[str], dict]


class HttpJsonFetcher:
    """Callable that GETs a URL and returns parsed JSON, with retry/backoff."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        retries: int = 3,
        backoff: float = 0.5,
        delay: float = 0.0,
        timeout: float = 15.0,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": "startup-agent/0.1"}
        )
        self._retries = retries
        self._backoff = backoff
        self._delay = delay

    def __call__(self, url: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._retries):
            try:
                response = self._client.get(url)
                response.raise_for_status()
                if self._delay:
                    time.sleep(self._delay)
                return response.json()
            except httpx.HTTPError as error:
                last_error = error
                if self._backoff:
                    time.sleep(self._backoff * (attempt + 1))
        assert last_error is not None
        raise last_error
```

- [ ] **Step 4: Run** `uv run pytest tests/adapters/ats/test_http_fetcher.py -v` → 3 passed.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/adapters/ats/__init__.py src/startup_agent/adapters/ats/http_fetcher.py tests/adapters/ats
git commit -m "feat: add HttpJsonFetcher (httpx GET with retry/backoff)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.3: GreenhouseAdapter

**Files:** Create `src/startup_agent/adapters/ats/greenhouse.py`; Test `tests/adapters/ats/test_greenhouse.py`

- [ ] **Step 1: Write the failing test** (uses the real fixture, offline)

```python
import json
from pathlib import Path

from startup_agent.adapters.ats.greenhouse import GreenhouseAdapter
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path("spike/fixtures/greenhouse_fireblocks.json")


def _stub_fetcher():
    payload = json.loads(FIXTURE.read_text())
    return lambda url: payload


def test_greenhouse_builds_correct_url_and_parses_jobs():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = GreenhouseAdapter(fetch_json=fetch)
    company = Company(name="Fireblocks", ats_type=AtsType.GREENHOUSE, ats_token="fireblocks")
    jobs = adapter.fetch_jobs(company)

    assert captured["url"] == "https://boards-api.greenhouse.io/v1/boards/fireblocks/jobs?content=true"
    assert len(jobs) == 50
    j = jobs[0]
    assert j.company_id == company.id_hash
    assert j.ats_job_id == "4655907006"          # int id -> str
    assert j.title == "AI Secops Tech-lead"
    assert j.location == "Tel Aviv-Yafo, Tel Aviv District, Israel"
    assert j.url.startswith("https://www.fireblocks.com/careers/position/4655907006")
    assert "digital assets" in (j.description or "")   # HTML entities unescaped
    assert "&lt;" not in (j.description or "")          # entities decoded
    assert j.posted_at is not None                      # from first_published


def test_greenhouse_handles_empty_board():
    adapter = GreenhouseAdapter(fetch_json=lambda url: {"jobs": []})
    company = Company(name="Empty", ats_type=AtsType.GREENHOUSE, ats_token="empty")
    assert adapter.fetch_jobs(company) == []
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`src/startup_agent/adapters/ats/greenhouse.py`)

```python
import html
from datetime import datetime

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job

_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class GreenhouseAdapter:
    ats_type = AtsType.GREENHOUSE

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("jobs", []):
            location = (raw.get("location") or {}).get("name")
            content = raw.get("content")
            jobs.append(
                Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["id"]),
                    title=raw["title"],
                    url=raw["absolute_url"],
                    location=location,
                    description=html.unescape(content) if content else None,
                    posted_at=_parse_dt(raw.get("first_published") or raw.get("updated_at")),
                )
            )
        return jobs
```

- [ ] **Step 4: Run** `uv run pytest tests/adapters/ats/test_greenhouse.py -v` → 2 passed.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/adapters/ats/greenhouse.py tests/adapters/ats/test_greenhouse.py
git commit -m "feat: add GreenhouseAdapter (parses real board payload into Job)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.4: AshbyAdapter

**Files:** Create `src/startup_agent/adapters/ats/ashby.py`; Test `tests/adapters/ats/test_ashby.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from startup_agent.adapters.ats.ashby import AshbyAdapter
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path("spike/fixtures/ashby_pinecone.json")


def test_ashby_builds_url_and_parses_jobs():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = AshbyAdapter(fetch_json=fetch)
    company = Company(name="Pinecone", ats_type=AtsType.ASHBY, ats_token="pinecone")
    jobs = adapter.fetch_jobs(company)

    assert captured["url"] == "https://api.ashbyhq.com/posting-api/job-board/pinecone"
    assert len(jobs) == 7
    j = jobs[0]
    assert j.company_id == company.id_hash
    assert j.ats_job_id == "7261adcb-026d-4552-8f89-7a46156c40c5"
    assert j.title == "Staff/Principal Product Manager, Database"
    assert j.location == "US Remote"
    assert j.url == "https://jobs.ashbyhq.com/pinecone/7261adcb-026d-4552-8f89-7a46156c40c5"
    assert "Pinecone" in (j.description or "")     # descriptionPlain
    assert j.posted_at is not None                  # publishedAt


def test_ashby_handles_empty_board():
    adapter = AshbyAdapter(fetch_json=lambda url: {"jobs": []})
    company = Company(name="Empty", ats_type=AtsType.ASHBY, ats_token="empty")
    assert adapter.fetch_jobs(company) == []
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`src/startup_agent/adapters/ats/ashby.py`)

```python
from datetime import datetime

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher, JsonFetcher
from startup_agent.domain.models import AtsType, Company, Job

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class AshbyAdapter:
    ats_type = AtsType.ASHBY

    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()

    def fetch_jobs(self, company: Company) -> list[Job]:
        payload = self._fetch(_BASE.format(token=company.ats_token))
        jobs: list[Job] = []
        for raw in payload.get("jobs", []):
            jobs.append(
                Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["id"]),
                    title=raw["title"],
                    url=raw.get("jobUrl") or raw.get("applyUrl"),
                    location=raw.get("location"),
                    description=raw.get("descriptionPlain"),
                    posted_at=_parse_dt(raw.get("publishedAt")),
                )
            )
        return jobs
```

- [ ] **Step 4: Run** → 2 passed.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/adapters/ats/ashby.py tests/adapters/ats/test_ashby.py
git commit -m "feat: add AshbyAdapter (parses real job-board payload into Job)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.5: ATSAdapterFactory (registry)

**Files:** Create `src/startup_agent/factories/__init__.py` (empty), `src/startup_agent/factories/ats_factory.py`; Test `tests/factories/__init__.py` (empty), `tests/factories/test_ats_factory.py`

- [ ] **Step 1: Write the failing test**

```python
from startup_agent.domain.models import AtsType, Company
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.adapters.ats.greenhouse import GreenhouseAdapter
from startup_agent.adapters.ats.ashby import AshbyAdapter


def test_factory_returns_adapter_per_ats_type():
    factory = ATSAdapterFactory()
    assert isinstance(factory.for_company(Company(name="A", ats_type=AtsType.GREENHOUSE)), GreenhouseAdapter)
    assert isinstance(factory.for_company(Company(name="B", ats_type=AtsType.ASHBY)), AshbyAdapter)


def test_factory_returns_none_for_unsupported():
    factory = ATSAdapterFactory()
    assert factory.for_company(Company(name="C", ats_type=AtsType.COMEET)) is None


def test_factory_supported_types():
    factory = ATSAdapterFactory()
    assert AtsType.GREENHOUSE in factory.supported_types()
    assert AtsType.ASHBY in factory.supported_types()
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`src/startup_agent/factories/ats_factory.py`)

```python
from startup_agent.adapters.ats.ashby import AshbyAdapter
from startup_agent.adapters.ats.greenhouse import GreenhouseAdapter
from startup_agent.adapters.ats.http_fetcher import JsonFetcher
from startup_agent.domain.models import AtsType, Company
from startup_agent.ports.ats import ATSAdapter

# Registry: add a new ATS by registering its adapter class here. Nothing else changes.
_REGISTRY: dict[AtsType, type] = {
    AtsType.GREENHOUSE: GreenhouseAdapter,
    AtsType.ASHBY: AshbyAdapter,
}


class ATSAdapterFactory:
    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch_json = fetch_json

    def for_company(self, company: Company) -> ATSAdapter | None:
        adapter_cls = _REGISTRY.get(company.ats_type)
        if adapter_cls is None:
            return None
        return adapter_cls(fetch_json=self._fetch_json)

    def supported_types(self) -> set[AtsType]:
        return set(_REGISTRY)
```

- [ ] **Step 4: Run** → 3 passed.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/factories tests/factories
git commit -m "feat: add ATSAdapterFactory (registry keyed by ats_type)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.6: ATS detection utility

**Files:** Create `src/startup_agent/companies/__init__.py` (empty), `src/startup_agent/companies/ats_detection.py`; Test `tests/companies/__init__.py` (empty), `tests/companies/test_ats_detection.py`

- [ ] **Step 1: Write the failing test**

```python
from startup_agent.companies.ats_detection import detect_ats
from startup_agent.domain.models import AtsType


def test_detect_greenhouse_both_url_forms():
    assert detect_ats("https://boards.greenhouse.io/fireblocks") == (AtsType.GREENHOUSE, "fireblocks")
    assert detect_ats("https://job-boards.greenhouse.io/melio") == (AtsType.GREENHOUSE, "melio")


def test_detect_ashby_lever_workable_comeet():
    assert detect_ats("https://jobs.ashbyhq.com/pinecone") == (AtsType.ASHBY, "pinecone")
    assert detect_ats("https://jobs.lever.co/acme") == (AtsType.LEVER, "acme")
    assert detect_ats("https://apply.workable.com/acme/") == (AtsType.WORKABLE, "acme")
    assert detect_ats("https://acme.workable.com") == (AtsType.WORKABLE, "acme")
    assert detect_ats("https://www.comeet.com/jobs/acme/12.34") == (AtsType.COMEET, "acme")


def test_detect_unknown():
    assert detect_ats("https://www.some-startup.com/careers") == (AtsType.UNKNOWN, None)
    assert detect_ats(None) == (AtsType.UNKNOWN, None)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`src/startup_agent/companies/ats_detection.py`)

```python
import re

from startup_agent.domain.models import AtsType

_PATTERNS: list[tuple[AtsType, re.Pattern]] = [
    (AtsType.GREENHOUSE, re.compile(r"(?:job-)?boards\.greenhouse\.io/([^/?#]+)")),
    (AtsType.ASHBY, re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)")),
    (AtsType.LEVER, re.compile(r"jobs\.lever\.co/([^/?#]+)")),
    (AtsType.WORKABLE, re.compile(r"apply\.workable\.com/([^/?#]+)")),
    (AtsType.WORKABLE, re.compile(r"([^/.]+)\.workable\.com")),
    (AtsType.SMARTRECRUITERS, re.compile(r"careers\.smartrecruiters\.com/([^/?#]+)")),
    (AtsType.COMEET, re.compile(r"comeet\.com/jobs/([^/?#]+)")),
]


def detect_ats(url: str | None) -> tuple[AtsType, str | None]:
    if not url:
        return (AtsType.UNKNOWN, None)
    for ats_type, pattern in _PATTERNS:
        match = pattern.search(url)
        if match:
            return (ats_type, match.group(1))
    return (AtsType.UNKNOWN, None)
```

- [ ] **Step 4: Run** → 3 passed.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/companies tests/companies
git commit -m "feat: add detect_ats URL->(ats_type, token) utility" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.7: Company seed + loader + `refresh-companies` CLI

**Files:** Create `data/companies.json`, `src/startup_agent/companies/loader.py`; Test `tests/companies/test_loader.py`; Modify `src/startup_agent/cli.py`

- [ ] **Step 1: Create `data/companies.json`** (curated verified set from the spike)

```json
[
  {"name": "Fireblocks", "website": "fireblocks.com", "ats_type": "greenhouse", "ats_token": "fireblocks"},
  {"name": "Melio", "website": "melio.com", "ats_type": "greenhouse", "ats_token": "melio"},
  {"name": "Riskified", "website": "riskified.com", "ats_type": "greenhouse", "ats_token": "riskified"},
  {"name": "Gong", "website": "gong.io", "ats_type": "greenhouse", "ats_token": "gongio"},
  {"name": "At-Bay", "website": "at-bay.com", "ats_type": "greenhouse", "ats_token": "atbay"},
  {"name": "Pinecone", "website": "pinecone.io", "ats_type": "ashby", "ats_token": "pinecone"},
  {"name": "Drata", "website": "drata.com", "ats_type": "ashby", "ats_token": "drata"},
  {"name": "Orca Security", "website": "orca.security", "ats_type": "ashby", "ats_token": "orca"},
  {"name": "Wiz", "website": "wiz.io", "ats_type": "ashby", "ats_token": "wiz"},
  {"name": "Snyk", "website": "snyk.io", "ats_type": "ashby", "ats_token": "snyk"}
]
```

- [ ] **Step 2: Write the failing test** (`tests/companies/test_loader.py`)

```python
import json

from startup_agent.companies.loader import load_companies_from_seed
from startup_agent.domain.models import AtsType


def test_loader_parses_seed(tmp_path):
    seed = tmp_path / "c.json"
    seed.write_text(json.dumps([
        {"name": "Fireblocks", "website": "fireblocks.com", "ats_type": "greenhouse", "ats_token": "fireblocks"},
        {"name": "Pinecone", "website": "pinecone.io", "ats_type": "ashby", "ats_token": "pinecone"},
    ]))
    companies = load_companies_from_seed(str(seed))
    assert len(companies) == 2
    assert companies[0].ats_type is AtsType.GREENHOUSE
    assert companies[1].ats_token == "pinecone"


def test_loader_defaults_missing_ats_to_unknown(tmp_path):
    seed = tmp_path / "c.json"
    seed.write_text(json.dumps([{"name": "Mystery", "website": "mystery.com"}]))
    companies = load_companies_from_seed(str(seed))
    assert companies[0].ats_type is AtsType.UNKNOWN
```

- [ ] **Step 3: Run** → FAIL.
- [ ] **Step 4: Implement** (`src/startup_agent/companies/loader.py`)

```python
import json
from pathlib import Path

from startup_agent.domain.models import AtsType, Company


def load_companies_from_seed(path: str) -> list[Company]:
    rows = json.loads(Path(path).read_text())
    companies: list[Company] = []
    for row in rows:
        ats_value = row.get("ats_type", "unknown")
        companies.append(
            Company(
                name=row["name"],
                website=row.get("website"),
                ats_type=AtsType(ats_value),
                ats_token=row.get("ats_token"),
            )
        )
    return companies
```

- [ ] **Step 5: Add the CLI command** (`src/startup_agent/cli.py`) — add this command and the imports it needs:

```python
from startup_agent.companies.loader import load_companies_from_seed


@app.command("refresh-companies")
def refresh_companies(
    db_path: str = typer.Option("jobs.db", "--db-path"),
    seed: str = typer.Option("data/companies.json", "--seed"),
) -> None:
    """Load the company seed file into the database."""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    companies = load_companies_from_seed(seed)
    for company in companies:
        repo.upsert_company(company)
    typer.echo(f"Loaded {len(companies)} companies into {db_path}")
```

- [ ] **Step 6: Run** `uv run pytest tests/companies/test_loader.py -v` → 2 passed. Smoke: `uv run startup-agent refresh-companies --db-path /tmp/c.db` → "Loaded 10 companies".
- [ ] **Step 7: Commit**

```bash
git add data/companies.json src/startup_agent/companies/loader.py tests/companies/test_loader.py src/startup_agent/cli.py
git commit -m "feat: add company seed loader + refresh-companies CLI" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.8: IngestionService + `run` CLI + end-to-end

**Files:** Create `src/startup_agent/services/__init__.py` (empty), `src/startup_agent/services/ingestion.py`; Test `tests/services/__init__.py` (empty), `tests/services/test_ingestion.py`; Modify `src/startup_agent/cli.py`

- [ ] **Step 1: Write the failing test** (offline — stub fetcher per company, fake repo via real in-memory SQLite)

```python
import json
from pathlib import Path

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import AtsType, Company
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.services.ingestion import IngestionService

GH = json.loads(Path("spike/fixtures/greenhouse_fireblocks.json").read_text())
ASHBY = json.loads(Path("spike/fixtures/ashby_pinecone.json").read_text())


def _routing_fetcher(url: str) -> dict:
    if "greenhouse" in url:
        return GH
    if "ashbyhq" in url:
        return ASHBY
    return {"jobs": []}


def _seeded_repo():
    repo = SQLiteJobRepository(":memory:")
    repo.init_schema()
    repo.upsert_company(Company(name="Fireblocks", ats_type=AtsType.GREENHOUSE, ats_token="fireblocks"))
    repo.upsert_company(Company(name="Pinecone", ats_type=AtsType.ASHBY, ats_token="pinecone"))
    repo.upsert_company(Company(name="ComeetCo", ats_type=AtsType.COMEET, ats_token="x"))  # unsupported -> skipped
    return repo


def test_ingestion_fetches_and_stores_new_jobs():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    service = IngestionService(repo=repo, factory=factory)

    report = service.run()
    assert report.companies_count == 3
    assert report.jobs_fetched == 57   # 50 greenhouse + 7 ashby
    assert report.jobs_new == 57
    assert report.status == "success"


def test_ingestion_is_idempotent_no_duplicate_new():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    service = IngestionService(repo=repo, factory=factory)

    service.run()
    second = service.run()
    assert second.jobs_fetched == 57
    assert second.jobs_new == 0        # all already seen -> dedup


def test_ingestion_isolates_company_failure():
    repo = _seeded_repo()

    def flaky_fetcher(url: str) -> dict:
        if "greenhouse" in url:
            raise RuntimeError("boom")
        return _routing_fetcher(url)

    factory = ATSAdapterFactory(fetch_json=flaky_fetcher)
    service = IngestionService(repo=repo, factory=factory)
    report = service.run()
    # greenhouse company failed, ashby still ingested
    assert report.jobs_new == 7
    assert report.status == "partial"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`src/startup_agent/services/ingestion.py`)

```python
import structlog

from startup_agent.domain.models import RunReport
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()


class IngestionService:
    def __init__(self, repo: JobRepository, factory: ATSAdapterFactory) -> None:
        self._repo = repo
        self._factory = factory

    def run(self) -> RunReport:
        companies = self._repo.get_companies()
        report = RunReport(companies_count=len(companies))
        had_failure = False

        for company in companies:
            adapter = self._factory.for_company(company)
            if adapter is None:
                logger.info("skip_unsupported_ats", company=company.name,
                            ats_type=company.ats_type.value)
                continue
            try:
                jobs = adapter.fetch_jobs(company)
            except Exception as error:  # per-company isolation
                had_failure = True
                logger.warning("fetch_failed", company=company.name, error=str(error))
                continue
            report.jobs_fetched += len(jobs)
            for job in jobs:
                if self._repo.upsert_job(job):
                    report.jobs_new += 1

        report.status = "partial" if had_failure else "success"
        self._repo.record_run(report)
        return report
```

- [ ] **Step 4: Add the `run` CLI command** (`src/startup_agent/cli.py`)

```python
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.services.ingestion import IngestionService


@app.command("run")
def run(db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Fetch new jobs from all companies into the database."""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    service = IngestionService(repo=repo, factory=ATSAdapterFactory())
    report = service.run()
    typer.echo(
        f"companies={report.companies_count} fetched={report.jobs_fetched} "
        f"new={report.jobs_new} status={report.status}"
    )
```

- [ ] **Step 5: Run** `uv run pytest tests/services -v` → 3 passed. Then FULL suite `uv run pytest -q` → all green. `uv run ruff check src tests` → clean.
- [ ] **Step 6: Commit**

```bash
git add src/startup_agent/services tests/services src/startup_agent/cli.py
git commit -m "feat: add IngestionService + run CLI (fetch+dedup, per-company isolation)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2.9: Live smoke + checkpoint

- [ ] **Step 1:** Live end-to-end against real ATS APIs (network):
  `uv run startup-agent refresh-companies --db-path /tmp/live.db`
  `uv run startup-agent run --db-path /tmp/live.db` → prints a summary with `new=` > 0.
- [ ] **Step 2:** Re-run `run` → `new=0` (idempotent dedup confirmed live).
- [ ] **Step 3:** Inspect: `sqlite3 /tmp/live.db "SELECT company_id, count(*) FROM jobs GROUP BY company_id"`.
- [ ] **Step 4:** Push branch, open PR, merge to `main`.

> **Checkpoint:** `main` now fetches real jobs end-to-end. STOP — Phase 3 (CV matching) plan is written next.

---

## Self-Review Notes

- **Spec coverage:** ATS-adapter factory (2.5), Greenhouse + Ashby adapters against real fixtures (2.3/2.4), company loader (2.7), ATS auto-detection utility (2.6), normalization-in-adapter + dedup end-to-end (2.8). HTTP politeness/retry (2.2). Per-company error isolation + run logging (2.8). Comeet/Lever/Workable + 247-list token discovery are explicitly out of scope (later phases).
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `JsonFetcher` (Callable[[str],dict]), `ATSAdapter.fetch_jobs -> list[Job]`, `ATSAdapterFactory(fetch_json=...)`/`for_company`/`supported_types`, `IngestionService(repo, factory).run() -> RunReport`, `load_companies_from_seed(path)`, `detect_ats(url) -> (AtsType, token|None)` — all used consistently.
- **Known real-data caveat:** Wiz/Snyk Ashby boards returned 0 live jobs during the spike (valid tokens, empty boards). That's fine — adapters handle empty boards (tested), and the live smoke total depends on what's posted that day.
