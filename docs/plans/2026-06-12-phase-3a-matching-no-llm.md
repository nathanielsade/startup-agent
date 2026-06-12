# Phase 3a Implementation Plan — Matching (free, no LLM)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** `startup-agent match` reads the user's CV, filters the stored jobs by hard preferences (seniority + location), ranks the survivors by **semantic similarity** between the CV and each job (local embeddings — no API, $0), and prints **every job above a similarity threshold** (no fixed cap). Stage 3b later adds the Claude scoring on top.

**Architecture:** Adds three things behind existing patterns: a `LocalEmbedder` implementing the `Embedder` port (sentence-transformers, runs locally), a `matching/` package (location classifier + preference prefilter + cosine ranking), and a `SimilarityMatchingService` that orchestrates filter → embed → rank → persist. CV text + embeddings are stored in SQLite (the `cv` table and the `jobs.embedding` column already exist). Preferences live in `data/preferences.yaml`.

**Tech Stack additions:** `sentence-transformers` (pulls torch — large one-time download; model `BAAI/bge-small-en-v1.5`, 384-dim, normalized), `pypdf` (CV parsing), `pyyaml` (preferences), `numpy` (cosine). Tests inject a tiny `FakeEmbedder` so the suite never loads the real model or hits the network.

**Workflow:** Branch `phase-3a/matching`. TDD per task, merge to `main` at the checkpoint.

## Key design decisions
- **No result cap.** Output = every candidate with cosine similarity ≥ `match_threshold` (configurable, default 0.30 — tuned during the live smoke). The threshold is the suitability bar, not a count.
- **Hard filters first** (cheap, deterministic): drop by seniority keyword in title, and by location region. *Unknown* location or *missing* fields → **kept** (never silently drop a possibly-suitable job).
- **Location rule** (as agreed): onsite/hybrid kept only if city ∈ **center**; **remote always kept**; North / South / **Jerusalem** dropped (when not remote). The hybrid>onsite>remote *ranking* preference is deferred to 3b (needs work-arrangement, which the LLM reads from the description).
- **Embeddings cached** in `jobs.embedding`; only un-embedded jobs are embedded each run.
- **Job text embedded** = `f"{title}\n{description}"` (description truncated to 2000 chars). CV text embedded whole. `normalize_embeddings=True` → cosine = dot product.

## File structure (new in 3a)
```
data/preferences.yaml
src/startup_agent/adapters/embedding/__init__.py
src/startup_agent/adapters/embedding/local_embedder.py     LocalEmbedder(Embedder)
src/startup_agent/adapters/embedding/serialization.py       vector <-> bytes (numpy float32)
src/startup_agent/cv/__init__.py
src/startup_agent/cv/loader.py                              read_pdf_text(path)
src/startup_agent/matching/__init__.py
src/startup_agent/matching/location.py                      classify_location, location_allowed
src/startup_agent/matching/prefilter.py                     passes_prefilter(job, prefs)
src/startup_agent/matching/similarity.py                    cosine(a, b)
src/startup_agent/services/matching.py                      SimilarityMatchingService
src/startup_agent/config/preferences_loader.py              load_preferences(path)
# repo extensions in adapters/storage/sqlite_repository.py + ports/repository.py
```

---

### Task 3a.1: Dependencies + settings

**Files:** Modify `pyproject.toml` (via uv), `src/startup_agent/config/settings.py`; Test `tests/config/test_settings.py`

- [ ] **Step 1:** Add deps: `uv add sentence-transformers pypdf pyyaml numpy`. (This downloads torch — expect a large, slow install. That's expected and one-time.)
- [ ] **Step 2: Failing test** — add to `tests/config/test_settings.py`:

```python
def test_settings_match_defaults(monkeypatch):
    monkeypatch.delenv("MATCH_THRESHOLD", raising=False)
    from startup_agent.config.settings import Settings
    s = Settings()
    assert s.match_threshold == 0.30
    assert s.preferences_path == "data/preferences.yaml"
```

- [ ] **Step 3:** Add to `Settings` (`config/settings.py`): `match_threshold: float = 0.30` and `preferences_path: str = "data/preferences.yaml"`.
- [ ] **Step 4:** `uv run pytest tests/config -v` → green.
- [ ] **Step 5: Commit** `chore: add embedding/pdf/yaml deps + match settings` (+ co-author trailer).

---

### Task 3a.2: Vector serialization

**Files:** Create `src/startup_agent/adapters/embedding/__init__.py` (empty), `src/startup_agent/adapters/embedding/serialization.py`; Test `tests/adapters/embedding/__init__.py` (empty), `tests/adapters/embedding/test_serialization.py`

- [ ] **Step 1: Failing test**

```python
from startup_agent.adapters.embedding.serialization import to_bytes, from_bytes


def test_vector_round_trips():
    vec = [0.1, -0.2, 0.3, 0.4]
    restored = from_bytes(to_bytes(vec))
    assert len(restored) == 4
    assert abs(restored[0] - 0.1) < 1e-6
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`serialization.py`)

```python
import numpy as np


def to_bytes(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> list[float]:
    return np.frombuffer(blob, dtype=np.float32).tolist()
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: add embedding vector serialization (numpy float32 <-> bytes)`.

---

### Task 3a.3: Cosine similarity

**Files:** Create `src/startup_agent/matching/__init__.py` (empty), `src/startup_agent/matching/similarity.py`; Test `tests/matching/__init__.py` (empty), `tests/matching/test_similarity.py`

- [ ] **Step 1: Failing test**

```python
from startup_agent.matching.similarity import cosine


def test_cosine_identical_is_one():
    assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-6


def test_cosine_orthogonal_is_zero():
    assert abs(cosine([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_cosine_handles_zero_vector():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`similarity.py`)

```python
import numpy as np


def cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: add cosine similarity`.

---

### Task 3a.4: Location classifier

**Files:** Create `src/startup_agent/matching/location.py`; Test `tests/matching/test_location.py`

- [ ] **Step 1: Failing test**

```python
from startup_agent.matching.location import classify_location, location_allowed, Region


def test_classifies_regions():
    assert classify_location("Tel Aviv-Yafo, Tel Aviv District, Israel") is Region.CENTER
    assert classify_location("Herzliya") is Region.CENTER
    assert classify_location("Haifa, Israel") is Region.NORTH
    assert classify_location("Yokneam") is Region.NORTH
    assert classify_location("Beer Sheva") is Region.SOUTH
    assert classify_location("Jerusalem") is Region.JERUSALEM
    assert classify_location("US Remote") is Region.REMOTE
    assert classify_location("Remote - Israel") is Region.REMOTE
    assert classify_location("London, UK") is Region.UNKNOWN
    assert classify_location(None) is Region.UNKNOWN


def test_location_allowed_rule():
    assert location_allowed("Tel Aviv") is True       # center
    assert location_allowed("Remote") is True          # remote always ok
    assert location_allowed("Haifa") is False          # north
    assert location_allowed("Beer Sheva") is False     # south
    assert location_allowed("Jerusalem") is False      # excluded
    assert location_allowed("London") is True          # unknown -> keep (don't miss)
    assert location_allowed(None) is True              # missing -> keep
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`location.py`)

```python
from enum import Enum


class Region(str, Enum):
    CENTER = "center"
    NORTH = "north"
    SOUTH = "south"
    JERUSALEM = "jerusalem"
    REMOTE = "remote"
    UNKNOWN = "unknown"


_CENTER = {
    "tel aviv", "tel aviv-yafo", "tel-aviv", "ramat gan", "givatayim", "herzliya",
    "petah tikva", "petach tikva", "bnei brak", "holon", "bat yam", "rishon lezion",
    "rishon le zion", "raanana", "ra'anana", "kfar saba", "hod hasharon", "netanya",
    "rehovot", "ness ziona", "nes ziona", "yehud", "or yehuda", "airport city",
    "lod", "ramla", "modiin", "modi'in", "petah-tikva",
}
_NORTH = {
    "haifa", "yokneam", "yoqneam", "caesarea", "nazareth", "karmiel", "tiberias",
    "migdal haemek", "kiryat shmona", "akko", "nesher", "tirat carmel", "afula",
}
_SOUTH = {
    "beer sheva", "be'er sheva", "beersheba", "kiryat gat", "ashdod", "ashkelon",
    "eilat", "dimona", "sderot", "yeruham", "ofakim",
}
_JERUSALEM = {"jerusalem", "yerushalayim"}


def classify_location(location: str | None) -> Region:
    if not location:
        return Region.UNKNOWN
    text = location.lower()
    if "remote" in text:
        return Region.REMOTE
    for city in _CENTER:
        if city in text:
            return Region.CENTER
    for city in _JERUSALEM:
        if city in text:
            return Region.JERUSALEM
    for city in _NORTH:
        if city in text:
            return Region.NORTH
    for city in _SOUTH:
        if city in text:
            return Region.SOUTH
    return Region.UNKNOWN


def location_allowed(location: str | None) -> bool:
    region = classify_location(location)
    return region not in (Region.NORTH, Region.SOUTH, Region.JERUSALEM)
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: add Israel location classifier + center-only rule`.

---

### Task 3a.5: Preferences file + loader + prefilter

**Files:** Create `data/preferences.yaml`, `src/startup_agent/config/preferences_loader.py`, `src/startup_agent/matching/prefilter.py`; Test `tests/config/test_preferences_loader.py`, `tests/matching/test_prefilter.py`

- [ ] **Step 1: Create `data/preferences.yaml`**

```yaml
roles:
  - Backend Engineer
  - Software Engineer
  - AI Engineer
  - LLM Engineer
  - GenAI Engineer
  - Platform Engineer
  - Infrastructure Engineer
  - Python Developer
  - Full Stack Engineer
seniority:
  - Junior
  - Entry-level
  - Associate
  - Mid-level
locations:
  - Center (Gush Dan / Sharon)
  - Remote
must_have: []
exclude:
  - Senior
  - Staff
  - Principal
  - Lead
  - Manager
  - Director
  - Head of
  - VP
  - Intern
  - Internship
```

- [ ] **Step 2: Failing tests**

`tests/config/test_preferences_loader.py`:
```python
from startup_agent.config.preferences_loader import load_preferences


def test_loads_preferences_yaml():
    prefs = load_preferences("data/preferences.yaml")
    assert "Senior" in prefs.exclude
    assert any("Full Stack" in r for r in prefs.roles)
```

`tests/matching/test_prefilter.py`:
```python
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.prefilter import passes_prefilter

PREFS = Preferences(exclude=["Senior", "Staff", "Manager", "Intern"])


def _job(title, location):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1", location=location)


def test_drops_excluded_seniority():
    assert passes_prefilter(_job("Senior Backend Engineer", "Tel Aviv"), PREFS) is False
    assert passes_prefilter(_job("Engineering Manager", "Tel Aviv"), PREFS) is False


def test_drops_excluded_location():
    assert passes_prefilter(_job("Backend Engineer", "Haifa"), PREFS) is False
    assert passes_prefilter(_job("Backend Engineer", "Jerusalem"), PREFS) is False


def test_keeps_central_and_remote_junior_roles():
    assert passes_prefilter(_job("Backend Engineer", "Tel Aviv"), PREFS) is True
    assert passes_prefilter(_job("Software Engineer", "Remote"), PREFS) is True
    assert passes_prefilter(_job("Backend Engineer", "London"), PREFS) is True   # unknown loc kept
```

- [ ] **Step 3: Implement**

`config/preferences_loader.py`:
```python
from pathlib import Path

import yaml

from startup_agent.domain.preferences import Preferences


def load_preferences(path: str) -> Preferences:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return Preferences(**{k: data.get(k, []) for k in
                          ("roles", "seniority", "locations", "must_have", "exclude")})
```

`matching/prefilter.py`:
```python
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.location import location_allowed


def passes_prefilter(job: Job, preferences: Preferences) -> bool:
    title = job.title.lower()
    if any(term.lower() in title for term in preferences.exclude):
        return False
    if not location_allowed(job.location):
        return False
    return True
```

- [ ] **Step 4: Run** `uv run pytest tests/config tests/matching -v` → green. **Step 5: Commit** `feat: add preferences.yaml + loader + prefilter (seniority/location)`.

---

### Task 3a.6: Repository extensions (CV + job embeddings + read jobs)

**Files:** Modify `src/startup_agent/ports/repository.py`, `src/startup_agent/adapters/storage/sqlite_repository.py`; Test `tests/adapters/storage/test_sqlite_repository.py`

- [ ] **Step 1: Failing tests** (append)

```python
def test_save_and_get_cv(repo):
    repo.save_cv(path="cv.pdf", text="backend engineer python", embedding=b"\x00\x01", model="bge")
    cv = repo.get_cv()
    assert cv["text"] == "backend engineer python"
    assert cv["embedding"] == b"\x00\x01"


def test_get_cv_none_when_empty(repo):
    assert repo.get_cv() is None


def test_set_and_read_job_embedding(repo):
    from startup_agent.domain.models import Company, Job
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job = Job(company_id=cid, ats_job_id="1", title="Backend", url="https://x/1")
    repo.upsert_job(job)
    repo.set_job_embedding(job.id, b"\x09\x09")
    jobs = repo.get_jobs()
    assert len(jobs) == 1
    assert repo.get_job_embedding(job.id) == b"\x09\x09"
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Add to the `JobRepository` ABC** (`ports/repository.py`):

```python
    @abstractmethod
    def save_cv(self, path: str, text: str, embedding: bytes | None, model: str) -> None: ...

    @abstractmethod
    def get_cv(self) -> dict | None: ...

    @abstractmethod
    def get_jobs(self) -> list["Job"]: ...

    @abstractmethod
    def set_job_embedding(self, job_id: str, embedding: bytes) -> None: ...

    @abstractmethod
    def get_job_embedding(self, job_id: str) -> bytes | None: ...
```

- [ ] **Step 4: Implement in `SQLiteJobRepository`** (add methods; reuse `_now`):

```python
    def save_cv(self, path: str, text: str, embedding: bytes | None, model: str) -> None:
        self._conn.execute("DELETE FROM cv")  # single-CV store; replace on save
        self._conn.execute(
            "INSERT INTO cv (path, text, embedding, model, updated_at) VALUES (?,?,?,?,?)",
            (path, text, embedding, model, _now()),
        )
        self._conn.commit()

    def get_cv(self) -> dict | None:
        row = self._conn.execute(
            "SELECT path, text, embedding, model FROM cv ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {"path": row["path"], "text": row["text"],
                "embedding": row["embedding"], "model": row["model"]}

    def get_jobs(self) -> list[Job]:
        rows = self._conn.execute(
            "SELECT company_id, ats_job_id, title, location, url, description, posted_at FROM jobs"
        ).fetchall()
        jobs: list[Job] = []
        for r in rows:
            jobs.append(Job(
                company_id=r["company_id"], ats_job_id=r["ats_job_id"], title=r["title"],
                location=r["location"], url=r["url"], description=r["description"],
                posted_at=datetime.fromisoformat(r["posted_at"]) if r["posted_at"] else None,
            ))
        return jobs

    def set_job_embedding(self, job_id: str, embedding: bytes) -> None:
        self._conn.execute("UPDATE jobs SET embedding = ? WHERE id = ?", (embedding, job_id))
        self._conn.commit()

    def get_job_embedding(self, job_id: str) -> bytes | None:
        row = self._conn.execute("SELECT embedding FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row["embedding"] if row else None
```

(`datetime` is already imported at the top of the module.)

- [ ] **Step 5: Run** `uv run pytest tests/adapters/storage -v` → green. **Step 6: Commit** `feat: repo support for CV storage + job embeddings + get_jobs`.

---

### Task 3a.7: LocalEmbedder + CV loader + `load-cv` CLI

**Files:** Create `src/startup_agent/cv/__init__.py` (empty), `src/startup_agent/cv/loader.py`, `src/startup_agent/adapters/embedding/local_embedder.py`; Modify `src/startup_agent/cli.py`; Test `tests/cv/__init__.py` (empty), `tests/cv/test_loader.py`

- [ ] **Step 1: Failing test** for the PDF reader (`tests/cv/test_loader.py`) — generate a tiny PDF in-test with pypdf so no fixture file is needed:

```python
from pypdf import PdfWriter

from startup_agent.cv.loader import read_pdf_text


def test_read_pdf_text_returns_string(tmp_path):
    # a blank page is enough to prove it parses without error and returns str
    pdf = tmp_path / "cv.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(pdf, "wb") as fh:
        writer.write(fh)
    text = read_pdf_text(str(pdf))
    assert isinstance(text, str)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**

`cv/loader.py`:
```python
from pypdf import PdfReader


def read_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)
```

`adapters/embedding/local_embedder.py`:
```python
from startup_agent.ports.embedder import Embedder


class LocalEmbedder(Embedder):
    """Embedder backed by a local sentence-transformers model (no API, offline)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self._model_name = model_name
        self._model = None  # lazy: don't load the model until first use

    def _ensure(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
```

- [ ] **Step 4: Add `load-cv` CLI** (`cli.py`):
```python
from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.config.settings import Settings
from startup_agent.cv.loader import read_pdf_text


@app.command("load-cv")
def load_cv(path: str = typer.Option(..., "--path"),
            db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Parse a CV PDF, embed it locally, and store it."""
    settings = Settings()
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    text = read_pdf_text(path)
    embedder = LocalEmbedder(settings.embedding_model)
    vector = embedder.embed([text])[0]
    repo.save_cv(path=path, text=text, embedding=to_bytes(vector), model=settings.embedding_model)
    typer.echo(f"Loaded CV ({len(text)} chars) and stored its embedding.")
```

- [ ] **Step 5: Run** `uv run pytest tests/cv -v` → green. (LocalEmbedder is NOT unit-tested with the real model — it's exercised in the live smoke; matching tests use a FakeEmbedder.) **Step 6: Commit** `feat: add LocalEmbedder + CV PDF loader + load-cv CLI`.

---

### Task 3a.8: SimilarityMatchingService + `match` CLI + checkpoint

**Files:** Create `src/startup_agent/services/matching.py`; Modify `src/startup_agent/cli.py`; Test `tests/services/test_matching.py`

- [ ] **Step 1: Failing test** (offline — FakeEmbedder, in-memory repo)

```python
from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job
from startup_agent.domain.preferences import Preferences
from startup_agent.services.matching import SimilarityMatchingService


class FakeEmbedder:
    """Maps text to a 2-D vector by keyword, so cosine is deterministic."""
    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            out.append([1.0, 0.0] if "backend" in tl else [0.0, 1.0])
        return out


def _repo_with_jobs():
    repo = SQLiteJobRepository(":memory:")
    repo.init_schema()
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    repo.save_cv(path="cv.pdf", text="backend python engineer",
                 embedding=to_bytes([1.0, 0.0]), model="fake")
    repo.upsert_job(Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                        url="https://x/1", location="Tel Aviv", description="backend role"))
    repo.upsert_job(Job(company_id=cid, ats_job_id="2", title="Sales Rep",
                        url="https://x/2", location="Tel Aviv", description="sales role"))
    repo.upsert_job(Job(company_id=cid, ats_job_id="3", title="Senior Backend Engineer",
                        url="https://x/3", location="Tel Aviv", description="backend role"))
    repo.upsert_job(Job(company_id=cid, ats_job_id="4", title="Backend Engineer",
                        url="https://x/4", location="Haifa", description="backend role"))
    return repo


def test_match_ranks_relevant_above_threshold_and_respects_filters():
    repo = _repo_with_jobs()
    prefs = Preferences(exclude=["Senior", "Manager", "Intern"])
    service = SimilarityMatchingService(repo=repo, embedder=FakeEmbedder(),
                                        preferences=prefs, threshold=0.5)
    results = service.run()
    titles = [job.title for job, score in results]
    # "Backend Engineer" in Tel Aviv passes (cosine 1.0); sales filtered by similarity;
    # senior dropped by prefilter; Haifa dropped by location.
    assert "Backend Engineer" in titles
    assert "Sales Rep" not in titles
    assert "Senior Backend Engineer" not in titles
    assert all(score >= 0.5 for _, score in results)


def test_match_returns_all_above_threshold_no_cap():
    repo = _repo_with_jobs()
    cid = repo.get_companies()[0].id_hash
    for i in range(30):
        repo.upsert_job(Job(company_id=cid, ats_job_id=f"x{i}", title="Backend Engineer",
                            url=f"https://x/x{i}", location="Remote", description="backend role"))
    service = SimilarityMatchingService(repo=repo, embedder=FakeEmbedder(),
                                        preferences=Preferences(exclude=["Senior"]), threshold=0.5)
    results = service.run()
    # all 31 backend roles (1 original Tel Aviv + 30 remote) returned — no cap
    assert len(results) >= 31
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`services/matching.py`)

```python
import structlog

from startup_agent.adapters.embedding.serialization import from_bytes, to_bytes
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.prefilter import passes_prefilter
from startup_agent.matching.similarity import cosine
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()


class SimilarityMatchingService:
    def __init__(self, repo: JobRepository, embedder: Embedder,
                 preferences: Preferences, threshold: float) -> None:
        self._repo = repo
        self._embedder = embedder
        self._preferences = preferences
        self._threshold = threshold

    def _job_vector(self, job: Job) -> list[float]:
        cached = self._repo.get_job_embedding(job.id)
        if cached is not None:
            return from_bytes(cached)
        text = f"{job.title}\n{(job.description or '')[:2000]}"
        vector = self._embedder.embed([text])[0]
        self._repo.set_job_embedding(job.id, to_bytes(vector))
        return vector

    def run(self) -> list[tuple[Job, float]]:
        cv = self._repo.get_cv()
        if cv is None or cv["embedding"] is None:
            raise RuntimeError("No CV loaded. Run 'startup-agent load-cv --path <pdf>' first.")
        cv_vector = from_bytes(cv["embedding"])

        candidates = [j for j in self._repo.get_jobs()
                      if passes_prefilter(j, self._preferences)]
        scored: list[tuple[Job, float]] = []
        for job in candidates:
            score = cosine(cv_vector, self._job_vector(job))
            if score >= self._threshold:
                scored.append((job, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        logger.info("match_complete", candidates=len(candidates), matched=len(scored))
        return scored
```

- [ ] **Step 4: Add `match` CLI** (`cli.py`)

```python
from startup_agent.config.preferences_loader import load_preferences
from startup_agent.services.matching import SimilarityMatchingService


@app.command("match")
def match(db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Rank stored jobs against the CV by similarity (no LLM)."""
    settings = Settings()
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    prefs = load_preferences(settings.preferences_path)
    embedder = LocalEmbedder(settings.embedding_model)
    service = SimilarityMatchingService(repo=repo, embedder=embedder,
                                        preferences=prefs, threshold=settings.match_threshold)
    results = service.run()
    names = {c.id_hash: c.name for c in repo.get_companies()}
    typer.echo(f"{len(results)} matching jobs (threshold {settings.match_threshold}):")
    for job, score in results:
        typer.echo(f"  [{score:.2f}] {job.title} @ {names.get(job.company_id, '?')} "
                   f"— {job.location or 'n/a'} — {job.url}")
```

- [ ] **Step 5: Run** `uv run pytest tests/services/test_matching.py -v` → green. Full suite `uv run pytest -q` → all green. `uv run ruff check src tests` → clean.
- [ ] **Step 6: Commit** `feat: add SimilarityMatchingService + match CLI (filter + embed + rank, no cap)`.

---

### Task 3a.9: Live smoke + checkpoint

- [ ] **Step 1:** Live run (downloads the embedding model on first use — slow once):
  `uv run startup-agent refresh-companies && uv run startup-agent run` (fetch jobs)
  `uv run startup-agent load-cv --path /Users/netanelsade/Downloads/Netanel_Sade.pdf`
  `uv run startup-agent match`
- [ ] **Step 2:** Eyeball the ranked output. **Tune `match_threshold`** (env `MATCH_THRESHOLD`) so the list is "all the jobs that genuinely suit" without obvious junk — record the chosen default.
- [ ] **Step 3:** Push branch, open PR, merge to `main`.

> **Checkpoint:** `main` now produces a ranked, filtered list of suitable jobs — free, no LLM. STOP. Stage 3b (Claude scoring + reasons) and Stage 4 (digest) come next.

---

## Self-Review Notes
- **Spec coverage:** CV parse+embed+store (3a.7), preferences (3a.5), seniority+location hard filters with the agreed center-only/remote-kept/Jerusalem-excluded rule (3a.4/3a.5), local embeddings (3a.7), cosine ranking with **no cap, threshold-based** (3a.3/3a.8), repo support (3a.6). Work-arrangement *ranking* (hybrid>onsite>remote) and the LLM scoring/reasons are explicitly deferred to 3b.
- **Placeholder scan:** none.
- **Type consistency:** `Embedder.embed(list[str])->list[list[float]]`, `to_bytes/from_bytes`, `cosine`, `classify_location/location_allowed`, `passes_prefilter(job, prefs)`, repo `save_cv/get_cv/get_jobs/set_job_embedding/get_job_embedding`, `SimilarityMatchingService(repo, embedder, preferences, threshold).run()->list[tuple[Job,float]]` — consistent across tasks.
- **Test isolation:** matching/embedder tests use `FakeEmbedder`; the real model is only loaded in the live smoke. PDF test generates its own blank PDF via pypdf.
