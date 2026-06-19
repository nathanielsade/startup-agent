# Smart LLM Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add provider-pluggable LLM fit-scoring (0–100 + reason) on top of embedding matching — auto for last-24h jobs during a run, and on-demand per job via a "Rate" button — with the API key from `.env`.

**Architecture:** Two `Ranker` adapters (Claude, OpenAI) chosen by config; a shared prompt builder that injects preferences; a `rescore_recent` service that LLM-scores the fresh subset and merges (LLM-rated first); a `POST /api/rate` route for on-demand single-job rating; the React result cards gain reasons + a Rate button. Embedding stays the free default; everything degrades cleanly when no key is set.

**Tech Stack:** Python 3.13, pydantic v2, anthropic + openai SDKs, FastAPI (SSE), React+Vite+TS. All backend tests run offline with mocked ranker clients (no key).

**Repo discipline:** Work ONLY in `/Users/netanelsade/projects/startup-agent`; never touch `/Users/netanelsade/conifers`. Branch `phase-8/llm-matching`. Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File structure
```
src/startup_agent/adapters/ranking/prompt.py        NEW: shared INSTRUCTIONS + preferences_clause + job_text
src/startup_agent/adapters/ranking/claude_ranker.py  MODIFY: prefs arg + shared prompt
src/startup_agent/adapters/ranking/openai_ranker.py  NEW: OpenAIRanker(Ranker)
src/startup_agent/ports/ranker.py                    MODIFY: rank(cv_text, jobs, preferences=None)
src/startup_agent/adapters/storage/sqlite_repository.py  ADD get_job(job_id)
src/startup_agent/ports/repository.py                ADD get_job
src/startup_agent/config/settings.py                 ADD llm_provider/openai_*/llm_recent_hours
src/startup_agent/services/recent_rescore.py          NEW: rescore_recent(...)
api/schemas.py                                       MODIFY: JobMatch +job_id/+reason/+rated; from_result helper
api/deps.py                                          ADD get_ranker()
api/matching_view.py                                 ADD match_pairs() (raw Job,score)
api/routes/run.py                                    MODIFY: rescore when ranker configured
api/routes/rate.py                                   NEW: POST /api/rate
api/main.py                                          mount rate router
frontend/src/api/client.ts                           JobMatch +fields, RunEvent +rating, rateJob()
frontend/src/components/JobCard.tsx                   rated vs unrated + Rate button
frontend/src/App.tsx                                 update a card after rate
```

---

### Task 1: Shared prompt builder + preferences in the Ranker

**Files:** Create `src/startup_agent/adapters/ranking/prompt.py`; Modify `src/startup_agent/ports/ranker.py`, `src/startup_agent/adapters/ranking/claude_ranker.py`; Test `tests/adapters/ranking/test_prompt.py`, update `tests/adapters/ranking/test_claude_ranker.py`.

- [ ] **Step 1: Write the failing test** (`tests/adapters/ranking/test_prompt.py`)

```python
from startup_agent.adapters.ranking.prompt import preferences_clause, job_text
from startup_agent.domain.preferences import Preferences
from startup_agent.domain.models import Job


def test_preferences_clause_summarizes_set_fields():
    p = Preferences(districts=["center"], max_years=3, roles=["backend", "ai"],
                    seniority=["junior", "mid"])
    clause = preferences_clause(p)
    assert "center" in clause.lower()
    assert "3" in clause
    assert "backend" in clause.lower()


def test_preferences_clause_empty_when_no_prefs():
    assert preferences_clause(Preferences()) == ""
    assert preferences_clause(None) == ""


def test_job_text_includes_title_and_location():
    j = Job(company_id="c", ats_job_id="1", title="Backend Engineer",
            url="https://x/1", location="Tel Aviv", description="build things")
    t = job_text(j)
    assert "Backend Engineer" in t
    assert "Tel Aviv" in t
```

- [ ] **Step 2: Run** `uv run pytest tests/adapters/ranking/test_prompt.py -v` → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/adapters/ranking/prompt.py`:

```python
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

INSTRUCTIONS = (
    "You are a job-matching assistant. Given a candidate's CV and a single job "
    "posting, score how well the job fits the candidate from 0 to 100 and give a "
    "one-line reason (max ~20 words). Weigh role, seniority, skills, and domain. "
    "Be strict: 70+ means a genuinely strong fit worth applying to; 40-69 a "
    "stretch; below 40 a poor fit."
)


def preferences_clause(preferences: Preferences | None) -> str:
    if preferences is None:
        return ""
    parts: list[str] = []
    if preferences.roles:
        parts.append("prefers roles in " + ", ".join(preferences.roles))
    if preferences.seniority:
        parts.append("seniority " + "/".join(preferences.seniority))
    if preferences.max_years is not None:
        parts.append(f"up to {preferences.max_years} years of experience")
    if preferences.districts:
        parts.append("districts " + ", ".join(preferences.districts))
    if not parts:
        return ""
    return "Candidate preferences: " + "; ".join(parts) + "."


def job_text(job: Job) -> str:
    return (
        f"Title: {job.title}\n"
        f"Location: {job.location or 'n/a'}\n\n"
        f"{(job.description or '')[:4000]}"
    )
```

- [ ] **Step 4: Update the Ranker port** (`src/startup_agent/ports/ranker.py`):

```python
from abc import ABC, abstractmethod

from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences


class Ranker(ABC):
    @abstractmethod
    def rank(self, cv_text: str, jobs: list[Job],
             preferences: Preferences | None = None) -> list[MatchResult]: ...
```

- [ ] **Step 5: Update ClaudeRanker** to take prefs + use the shared prompt — replace `src/startup_agent/adapters/ranking/claude_ranker.py`:

```python
import anthropic
from pydantic import BaseModel, Field

from startup_agent.adapters.ranking.prompt import INSTRUCTIONS, job_text, preferences_clause
from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.ranker import Ranker


class _Score(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


class ClaudeRanker(Ranker):
    def __init__(self, api_key: str = "", model: str = "claude-opus-4-8",
                 client: object | None = None) -> None:
        self._client = client or (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self._model = model

    def rank(self, cv_text: str, jobs: list[Job],
             preferences: Preferences | None = None) -> list[MatchResult]:
        instructions = INSTRUCTIONS
        clause = preferences_clause(preferences)
        if clause:
            instructions = f"{INSTRUCTIONS}\n\n{clause}"
        results: list[MatchResult] = []
        for job in jobs:
            message = self._client.messages.parse(
                model=self._model,
                max_tokens=1000,
                system=[
                    {"type": "text", "text": instructions},
                    {"type": "text", "text": f"CANDIDATE CV:\n{cv_text}",
                     "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user",
                           "content": f"JOB POSTING:\n{job_text(job)}\n\nScore this job for the candidate."}],
                output_format=_Score,
            )
            parsed = message.parsed_output
            results.append(MatchResult(job_id=job.id, score=parsed.score,
                                       reason=parsed.reason, stage="llm"))
        return results
```

- [ ] **Step 6: Update the ClaudeRanker test** — in `tests/adapters/ranking/test_claude_ranker.py`, add a test that the preferences clause reaches the system text (the existing fake client captures `kwargs`):

```python
def test_claude_ranker_injects_preferences_into_prompt():
    from startup_agent.domain.preferences import Preferences
    client = _FakeClient()
    ranker = ClaudeRanker(client=client, model="claude-opus-4-8")
    ranker.rank("cv", [_job("Backend Engineer")], Preferences(roles=["backend"], max_years=3))
    system_texts = [b["text"] for b in client.messages.calls[0]["system"]]
    assert any("backend" in t.lower() for t in system_texts)
    assert any("3 years" in t for t in system_texts)
```

- [ ] **Step 7: Run** `uv run pytest tests/adapters/ranking -v` → PASS. Full suite `uv run pytest -q` → green (HybridMatchingService still calls `rank(cv, jobs)` with prefs defaulting to None — unaffected).
- [ ] **Step 8: Commit**

```bash
git add src/startup_agent/adapters/ranking/prompt.py src/startup_agent/ports/ranker.py src/startup_agent/adapters/ranking/claude_ranker.py tests/adapters/ranking
git commit -m "feat: shared ranker prompt + preferences injected into ClaudeRanker" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: OpenAIRanker

**Files:** Create `src/startup_agent/adapters/ranking/openai_ranker.py`; Test `tests/adapters/ranking/test_openai_ranker.py`. Modify `pyproject.toml` (uv add openai).

- [ ] **Step 1: Add dep** — `cd /Users/netanelsade/projects/startup-agent && uv add openai`.
- [ ] **Step 2: Write the failing test** (`tests/adapters/ranking/test_openai_ranker.py`) — a fake client mirroring `client.chat.completions.create(...).choices[0].message.content`:

```python
import json
from types import SimpleNamespace

from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences


def _job(title="Backend Engineer"):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location="Tel Aviv", description="build backend services")


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"score": 82, "reason": "strong backend fit"})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_openai_ranker_returns_match_results():
    client = _FakeClient()
    ranker = OpenAIRanker(client=client, model="gpt-4o")
    results = ranker.rank("backend cv", [_job()], Preferences(roles=["backend"]))
    assert len(results) == 1
    assert results[0].score == 82
    assert results[0].reason == "strong backend fit"
    assert results[0].stage == "llm"
    assert results[0].job_id == _job().id


def test_openai_ranker_injects_prefs_and_cv():
    client = _FakeClient()
    OpenAIRanker(client=client, model="gpt-4o").rank(
        "MY CV", [_job()], Preferences(roles=["backend"], max_years=3))
    msgs = client.chat.completions.calls[0]["messages"]
    blob = " ".join(m["content"] for m in msgs)
    assert "MY CV" in blob
    assert "backend" in blob.lower()
    assert "Backend Engineer" in blob
```

- [ ] **Step 3: Run** → FAIL.
- [ ] **Step 4: Implement** `src/startup_agent/adapters/ranking/openai_ranker.py`:

```python
import json

from startup_agent.adapters.ranking.prompt import INSTRUCTIONS, job_text, preferences_clause
from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.ranker import Ranker


class OpenAIRanker(Ranker):
    def __init__(self, api_key: str = "", model: str = "gpt-4o",
                 base_url: str = "", client: object | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)
        self._model = model

    def rank(self, cv_text: str, jobs: list[Job],
             preferences: Preferences | None = None) -> list[MatchResult]:
        instructions = INSTRUCTIONS
        clause = preferences_clause(preferences)
        if clause:
            instructions = f"{INSTRUCTIONS}\n\n{clause}"
        instructions += (
            '\n\nRespond ONLY with JSON: {"score": <int 0-100>, "reason": "<one line>"}'
        )
        results: list[MatchResult] = []
        for job in jobs:
            completion = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user",
                     "content": f"CANDIDATE CV:\n{cv_text}\n\nJOB POSTING:\n{job_text(job)}\n\nScore this job."},
                ],
            )
            data = json.loads(completion.choices[0].message.content)
            score = max(0, min(100, int(data.get("score", 0))))
            results.append(MatchResult(job_id=job.id, score=score,
                                       reason=str(data.get("reason", "")), stage="llm"))
        return results
```

- [ ] **Step 5: Run** `uv run pytest tests/adapters/ranking/test_openai_ranker.py -v` → 2 passed.
- [ ] **Step 6: Commit** `feat: add OpenAIRanker (provider-pluggable, JSON output)`.

---

### Task 3: Settings + get_ranker()

**Files:** Modify `src/startup_agent/config/settings.py`, `api/deps.py`; Test `tests/api/test_get_ranker.py`, append to `tests/config/test_settings.py`.

- [ ] **Step 1: Settings test** (append to `tests/config/test_settings.py`)

```python
def test_settings_llm_provider_defaults(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    from startup_agent.config.settings import Settings
    s = Settings()
    assert s.llm_provider == "anthropic"
    assert s.llm_recent_hours == 24
    assert s.openai_model == "gpt-4o"
```

- [ ] **Step 2: Add to `Settings`** (`config/settings.py`):

```python
    llm_provider: str = "anthropic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = ""
    llm_recent_hours: int = 24
```

- [ ] **Step 3: get_ranker test** (`tests/api/test_get_ranker.py`)

```python
from startup_agent.config.settings import Settings
from api.deps import build_ranker


def test_build_ranker_none_without_key():
    s = Settings(llm_provider="anthropic", anthropic_api_key="")
    assert build_ranker(s) is None


def test_build_ranker_anthropic_with_key():
    from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
    s = Settings(llm_provider="anthropic", anthropic_api_key="sk-test", llm_model="claude-opus-4-8")
    assert isinstance(build_ranker(s), ClaudeRanker)


def test_build_ranker_openai_with_key():
    from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
    s = Settings(llm_provider="openai", openai_api_key="sk-test", openai_model="gpt-4o")
    assert isinstance(build_ranker(s), OpenAIRanker)
```

- [ ] **Step 4: Run** → FAIL.
- [ ] **Step 5: Implement** in `api/deps.py` (add):

```python
def build_ranker(settings):
    """Return a configured Ranker, or None when no key is present."""
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        if not settings.openai_api_key:
            return None
        from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
        return OpenAIRanker(api_key=settings.openai_api_key, model=settings.openai_model,
                            base_url=settings.openai_base_url)
    if not settings.anthropic_api_key:
        return None
    from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
    return ClaudeRanker(api_key=settings.anthropic_api_key, model=settings.llm_model)


def get_ranker():
    return build_ranker(get_settings())
```

- [ ] **Step 6: Run** `uv run pytest tests/api/test_get_ranker.py tests/config -v` → PASS.
- [ ] **Step 7: Commit** `feat: LLM provider settings + build_ranker/get_ranker selector`.

---

### Task 4: JobMatch carries job_id/reason/rated

**Files:** Modify `api/schemas.py`; Test `tests/api/test_matching_view.py` (append).

- [ ] **Step 1: Write the failing test**

```python
def test_job_match_has_job_id_and_rated_defaults():
    from datetime import datetime, timezone
    from startup_agent.domain.models import Job
    from api.schemas import to_job_match
    job = Job(company_id="c1", ats_job_id="1", title="Backend Engineer",
              url="https://x/1", location="Tel Aviv", posted_at=datetime.now(timezone.utc))
    m = to_job_match(job, 0.73, {"c1": "Acme"})
    assert m.job_id == job.id
    assert m.rated is False
    assert m.reason is None


def test_job_match_from_result():
    from startup_agent.domain.models import Job, MatchResult
    from api.schemas import job_match_from_result
    job = Job(company_id="c1", ats_job_id="1", title="Backend Engineer", url="https://x/1",
              location="Tel Aviv")
    result = MatchResult(job_id=job.id, score=88, reason="great fit", stage="llm")
    m = job_match_from_result(job, result, {"c1": "Acme"})
    assert m.score == 88
    assert m.reason == "great fit"
    assert m.rated is True
    assert m.job_id == job.id
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — update `api/schemas.py`:

```python
from startup_agent.domain.models import Job, MatchResult


class JobMatch(BaseModel):
    job_id: str
    title: str
    company: str
    location: str | None
    score: int
    url: str
    posted_at: str | None
    age_label: str
    reason: str | None = None
    rated: bool = False
```

Update `to_job_match` to set `job_id=job.id`. Add:

```python
def job_match_from_result(job: Job, result: MatchResult, company_names: dict[str, str],
                          now: datetime | None = None) -> JobMatch:
    base = to_job_match(job, 0.0, company_names, now)
    return base.model_copy(update={"score": result.score, "reason": result.reason,
                                   "rated": True})
```

(Set `job_id=job.id` inside `to_job_match`'s constructor call.)

- [ ] **Step 4: Run** `uv run pytest tests/api/test_matching_view.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: JobMatch gains job_id/reason/rated + from_result helper`.

---

### Task 5: repo.get_job(job_id)

**Files:** Modify `src/startup_agent/ports/repository.py`, `src/startup_agent/adapters/storage/sqlite_repository.py`; Test `tests/adapters/storage/test_sqlite_repository.py` (append).

- [ ] **Step 1: Write the failing test**

```python
def test_get_job_by_id(repo):
    from startup_agent.domain.models import Company, Job
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job = Job(company_id=cid, ats_job_id="1", title="Backend", url="https://x/1")
    repo.upsert_job(job)
    got = repo.get_job(job.id)
    assert got is not None and got.title == "Backend"
    assert repo.get_job("nope") is None
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — add abstract `get_job(self, job_id: str) -> "Job | None"` to `JobRepository`, and in `SQLiteJobRepository`:

```python
    def get_job(self, job_id: str):
        from datetime import datetime
        row = self._conn.execute(
            "SELECT company_id, ats_job_id, title, location, url, description, posted_at "
            "FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return Job(
            company_id=row["company_id"], ats_job_id=row["ats_job_id"], title=row["title"],
            location=row["location"], url=row["url"], description=row["description"],
            posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
        )
```

(`Job` is already imported at the top of the module.)

- [ ] **Step 4: Run** `uv run pytest tests/adapters/storage -v` → PASS.
- [ ] **Step 5: Commit** `feat: repo.get_job(job_id)`.

---

### Task 6: rescore_recent service + match_pairs

**Files:** Create `src/startup_agent/services/recent_rescore.py`; Modify `api/matching_view.py`; Test `tests/services/test_recent_rescore.py`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta, timezone

from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.services.recent_rescore import rescore_recent

NOW = datetime(2026, 6, 19, 12, tzinfo=timezone.utc)


def _job(ats_id, title, posted_hours_ago):
    return Job(company_id="c1", ats_job_id=ats_id, title=title, url=f"https://x/{ats_id}",
               location="Tel Aviv", posted_at=NOW - timedelta(hours=posted_hours_ago))


class _FakeRanker:
    def rank(self, cv_text, jobs, preferences=None):
        return [MatchResult(job_id=j.id, score=90, reason="llm says fit", stage="llm") for j in jobs]


def test_only_recent_jobs_get_llm_scored_and_sorted_first():
    fresh = _job("1", "Backend Engineer", posted_hours_ago=5)    # within 24h
    old = _job("2", "Data Engineer", posted_hours_ago=100)        # outside 24h
    pairs = [(old, 0.80), (fresh, 0.50)]   # embedding had old higher
    out = rescore_recent(pairs, ranker=_FakeRanker(), cv_text="cv",
                         preferences=Preferences(), recent_hours=24,
                         company_names={"c1": "Acme"}, now=NOW)
    # fresh got LLM-rated (90) and sorts first despite lower embedding
    assert out[0].job_id == fresh.id
    assert out[0].rated is True and out[0].score == 90 and out[0].reason == "llm says fit"
    # old kept embedding score, not rated
    assert out[1].job_id == old.id
    assert out[1].rated is False and out[1].score == 80


def test_ranker_failure_keeps_embedding_score():
    class _BoomRanker:
        def rank(self, *a, **k):
            raise RuntimeError("boom")
    fresh = _job("1", "Backend Engineer", posted_hours_ago=5)
    out = rescore_recent([(fresh, 0.50)], ranker=_BoomRanker(), cv_text="cv",
                         preferences=Preferences(), recent_hours=24,
                         company_names={"c1": "Acme"}, now=NOW)
    assert out[0].rated is False and out[0].score == 50
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/services/recent_rescore.py`:

```python
from datetime import datetime, timedelta, timezone

import structlog

from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

from api.schemas import JobMatch, job_match_from_result, to_job_match

logger = structlog.get_logger()


def _is_recent(job: Job, now: datetime, recent_hours: int) -> bool:
    if job.posted_at is None:
        return False
    return (now - job.posted_at.astimezone(timezone.utc)) <= timedelta(hours=recent_hours)


def rescore_recent(pairs: list[tuple[Job, float]], ranker, cv_text: str,
                   preferences: Preferences, recent_hours: int,
                   company_names: dict[str, str], now: datetime | None = None) -> list[JobMatch]:
    now = now or datetime.now(timezone.utc)
    rated: list[JobMatch] = []
    unrated: list[JobMatch] = []
    for job, score in pairs:
        if _is_recent(job, now, recent_hours):
            try:
                result = ranker.rank(cv_text, [job], preferences)[0]
                rated.append(job_match_from_result(job, result, company_names, now))
                continue
            except Exception as error:  # keep embedding score on failure
                logger.warning("rate_failed", job=job.title, error=str(error))
        unrated.append(to_job_match(job, score, company_names, now))
    rated.sort(key=lambda m: m.score, reverse=True)
    unrated.sort(key=lambda m: m.score, reverse=True)
    return rated + unrated
```

- [ ] **Step 4: Add `match_pairs` to `api/matching_view.py`** (raw Job/score, for rescore):

```python
def match_pairs(repo, embedder, preferences_path, threshold):
    from startup_agent.services.matching import SimilarityMatchingService
    prefs = _load_prefs(repo, preferences_path)
    return SimilarityMatchingService(
        repo=repo, embedder=embedder, preferences=prefs, threshold=threshold
    ).run()
```

- [ ] **Step 5: Run** `uv run pytest tests/services/test_recent_rescore.py -v` → PASS. Full suite green.
- [ ] **Step 6: Commit** `feat: rescore_recent (LLM-score last-24h jobs, merge rated-first)`.

---

### Task 7: Wire run route + POST /api/rate

**Files:** Modify `api/routes/run.py`, `api/main.py`; Create `api/routes/rate.py`; Test `tests/api/test_rate.py`, update `tests/api/test_run.py`.

- [ ] **Step 1: Update run route** — in `api/routes/run.py`, add `get_ranker` to deps and rescore when configured. Replace the worker's match section:

```python
from api.deps import get_embedder, get_factory, get_ranker, get_settings
from api.matching_view import match_pairs, _load_prefs
from startup_agent.services.recent_rescore import rescore_recent
# ...
@router.get("/run")
def run(factory=Depends(get_factory), embedder=Depends(get_embedder),
        ranker=Depends(get_ranker), settings=Depends(get_settings)) -> StreamingResponse:
    # ... precheck unchanged ...
    def worker():
        try:
            repo = SQLiteJobRepository(settings.db_path)
            repo.init_schema()
            IngestionService(repo=repo, factory=factory).run(
                progress=lambda ev: events.put({"stage": "fetching", **ev}))
            pairs = match_pairs(repo, embedder, settings.preferences_path, settings.match_threshold)
            events.put({"stage": "matching", "candidates": len(pairs)})
            names = {c.id_hash: c.name for c in repo.get_companies()}
            if ranker is not None:
                events.put({"stage": "rating", "count": len(pairs)})
                cv = repo.get_cv()
                prefs = _load_prefs(repo, settings.preferences_path)
                matches = rescore_recent(pairs, ranker, cv["text"], prefs,
                                         settings.llm_recent_hours, names)
            else:
                from api.schemas import to_job_match
                matches = sorted([to_job_match(j, s, names) for j, s in pairs],
                                 key=lambda m: m.score, reverse=True)
            events.put({"stage": "done", "matched": len(matches),
                        "matches": [m.model_dump() for m in matches]})
        except Exception as error:  # noqa: BLE001
            events.put({"stage": "error", "message": str(error)})
        finally:
            events.put(_SENTINEL)
    # ... thread + stream unchanged ...
```

- [ ] **Step 2: Create `api/routes/rate.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository

from api.deps import get_ranker, get_settings
from api.matching_view import _load_prefs


class RateRequest(BaseModel):
    job_id: str


router = APIRouter()


@router.post("/rate")
def rate(body: RateRequest, ranker=Depends(get_ranker), settings=Depends(get_settings)) -> dict:
    if ranker is None:
        raise HTTPException(status_code=400, detail="No LLM configured. Add a key to .env.")
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    job = repo.get_job(body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    prefs = _load_prefs(repo, settings.preferences_path)
    result = ranker.rank(cv["text"], [job], prefs)[0]
    return {"score": result.score, "reason": result.reason}
```

Mount in `api/main.py` (`from api.routes import ..., rate` + `app.include_router(rate.router, prefix="/api")`).

- [ ] **Step 3: Write the rate test** (`tests/api/test_rate.py`)

```python
import io
from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, AtsType, MatchResult


def _pdf():
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    b = io.BytesIO(); w.write(b); return b.getvalue()


class _FakeRanker:
    def rank(self, cv_text, jobs, preferences=None):
        return [MatchResult(job_id=j.id, score=88, reason="strong fit", stage="llm") for j in jobs]


def _seed(settings):
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    cid = repo.get_companies()[0].id_hash
    job = Job(company_id=cid, ats_job_id="1", title="Backend Engineer", url="https://x/1",
              location="Tel Aviv", description="backend")
    repo.upsert_job(job)
    return job


def test_rate_returns_score_and_reason(client, settings):
    job = _seed(settings)
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_ranker] = lambda: _FakeRanker()
    resp = client.post("/api/rate", json={"job_id": job.id})
    assert resp.status_code == 200
    assert resp.json() == {"score": 88, "reason": "strong fit"}


def test_rate_without_ranker_returns_400(client, settings):
    job = _seed(settings)
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_ranker] = lambda: None
    resp = client.post("/api/rate", json={"job_id": job.id})
    assert resp.status_code == 400
```

(`tests/api/conftest.py` already clears `dependency_overrides` after each test.)

- [ ] **Step 4: Run** `uv run pytest tests/api -v && uv run pytest -q` → green. `uv run ruff check src api tests`.
- [ ] **Step 5: Commit** `feat: run route LLM-rescore + POST /api/rate (on-demand job rating)`.

---

### Task 8: Frontend — reasons + Rate button + rating stage

**Files:** Modify `frontend/src/api/client.ts`, `frontend/src/components/JobCard.tsx`, `frontend/src/components/RunProgress.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/app.css`.

- [ ] **Step 1: client.ts** — extend types + add `rateJob`:

```ts
export interface JobMatch {
  job_id: string;
  title: string;
  company: string;
  location: string | null;
  score: number;
  url: string;
  posted_at: string | null;
  age_label: string;
  reason: string | null;
  rated: boolean;
}

export type RunEvent =
  | { stage: "fetching"; done: number; total: number; company: string; jobs_fetched: number; jobs_new: number }
  | { stage: "matching"; candidates: number }
  | { stage: "rating"; count: number }
  | { stage: "done"; matched: number; matches: JobMatch[] }
  | { stage: "error"; message: string };

export async function rateJob(jobId: string): Promise<{ score: number; reason: string }> {
  const resp = await fetch("/api/rate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail || `Rate failed (${resp.status})`);
  }
  return resp.json();
}
```

- [ ] **Step 2: JobCard.tsx** — show reason + ✨ when rated; else a Rate button:

```tsx
import { useState } from "react";
import { rateJob, type JobMatch } from "../api/client";

export function JobCard({ job }: { job: JobMatch }) {
  const [j, setJ] = useState(job);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function rate() {
    setBusy(true); setErr(null);
    try {
      const r = await rateJob(j.job_id);
      setJ({ ...j, score: r.score, reason: r.reason, rated: true });
    } catch (e) { setErr(e instanceof Error ? e.message : "Rate failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="card">
      <div className="card-top">
        <b>{j.title}</b>
        <span className={`score ${j.rated ? "score-ai" : ""}`}>{j.rated ? `✨ ${j.score}` : j.score}</span>
      </div>
      <div className="muted">
        {j.company}{j.location ? ` · ${j.location}` : ""}{j.age_label ? ` · ${j.age_label}` : ""}
      </div>
      {j.reason && <div className="reason">{j.reason}</div>}
      <div className="card-actions">
        <a className="apply" href={j.url} target="_blank" rel="noreferrer">Apply →</a>
        {!j.rated && <button className="rate-btn" onClick={rate} disabled={busy}>
          {busy ? "Rating…" : "✨ Rate"}</button>}
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  );
}
```

- [ ] **Step 3: RunProgress.tsx** — handle the `rating` stage (add a branch):

```tsx
  if (last.stage === "rating") return <p className="muted">Rating {last.count} fresh jobs with AI…</p>;
```

(Place it alongside the existing `matching` branch.)

- [ ] **Step 4: app.css** — add styles:

```css
.score-ai { background: #4f46e5; color: #fff; }
.reason { margin-top: 6px; font-size: 13px; color: #374151; font-style: italic; }
.card-actions { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
.rate-btn { background: var(--accent-soft); color: var(--accent); border: 1px solid #c7d2fe; border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.rate-btn:disabled { opacity: .6; cursor: default; }
```

- [ ] **Step 5: Build** `cd frontend && npm run build` → clean (JobList passes `JobMatch` to JobCard; types line up).
- [ ] **Step 6: Commit** `feat(web): LLM reasons, ✨ AI score, and per-job Rate button`.

---

### Task 9: Live smoke + checkpoint

- [ ] **Step 1:** Backend suite + lint: `uv run pytest -q && uv run ruff check src api tests` → green.
- [ ] **Step 2 (no key):** `make dev`, run a search — confirm it still works on embedding only, and a job card's "✨ Rate" button shows the "No LLM configured" message (until a key is set).
- [ ] **Step 3 (with key, if available):** add `ANTHROPIC_API_KEY` to `.env`, restart backend, run — confirm last-24h jobs show ✨ AI scores + reasons at the top, and "✨ Rate" on an older card returns a score+reason. (Optional: set `LLM_PROVIDER=openai` + `OPENAI_API_KEY` to verify the OpenAI path.)
- [ ] **Step 4:** Merge `phase-8/llm-matching` → `main`.

> **Checkpoint:** provider-pluggable LLM scoring — auto on fresh jobs + on-demand per job — with reasons in the UI. Key-optional; embedding remains the free default.

---

## Self-Review Notes

- **Spec coverage:** key from .env / no UI secret (§2 → settings + build_ranker, no key UI); provider-pluggable Claude+OpenAI behind `Ranker` (§2 → Tasks 1,2,3); batch on last-24h (§3 → Task 6 `rescore_recent` + Task 7 run wiring, `llm_recent_hours`); per-job Rate (§3 → Task 7 `/api/rate` + Task 8 button); two-scores honest, LLM-rated first (§4 → `rescore_recent` ordering); prefs in prompt (§4 → Task 1 `preferences_clause`); architecture ports/adapters/services/api/frontend/settings (§5 → all tasks); error handling no-key/per-job-failure/malformed/cost-guard (§7 → build_ranker None, rescore try/except, OpenAI clamp+ClaudeParse, recency bound); testing offline mocked (§8 → every task); scope CV→prefs deferred (§9 → not in plan).
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `Ranker.rank(cv_text, jobs, preferences=None)` consistent across port, ClaudeRanker, OpenAIRanker, fakes, rescore. `JobMatch` fields (job_id/title/company/location/score/url/posted_at/age_label/reason/rated) identical in schemas.py + client.ts. `build_ranker(settings)`/`get_ranker()`, `match_pairs(...)`, `rescore_recent(pairs, ranker, cv_text, preferences, recent_hours, company_names, now)`, `repo.get_job(job_id)`, `MatchResult(job_id, score, reason, stage)`, `/api/rate {job_id}` — consistent across tasks. `RunEvent` stages (fetching/matching/rating/done/error) consistent run.py ↔ client.ts ↔ RunProgress.
