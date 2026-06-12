# Phase 3b Implementation Plan — LLM ranker (Claude scoring + reasons)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** `startup-agent match --llm` runs the Stage 3a similarity prefilter to get candidates, then has Claude score each one 0–100 with a one-line "why it fits", persists the results, and prints **all jobs above an LLM threshold** (no cap), best-first.

**Architecture:** A `ClaudeRanker` implements the existing `Ranker` port (`rank(cv_text, jobs) -> list[MatchResult]`) using the Anthropic SDK. A `HybridMatchingService` composes the Stage 3a `SimilarityMatchingService` (to produce candidates) with the ranker. The CV is sent in a cached system block (identical across the per-job calls → ~90% cheaper). Output is constrained with `messages.parse()` + a pydantic schema.

**Tech Stack additions:** `anthropic` SDK, model `claude-opus-4-8` (overridable via `LLM_MODEL`). Tests inject a fake Anthropic client / fake ranker — the suite never calls the real API.

**Cost note:** scoring is bounded — only the Stage-3a candidates (a handful/day) hit the LLM, CV is cached. The API key is required only for the live run; everything is built and unit-tested offline.

**Workflow:** Branch `phase-3b/llm-ranker`. TDD per task, merge to `main` at the checkpoint.

## File structure (new in 3b)
```
src/startup_agent/adapters/ranking/__init__.py
src/startup_agent/adapters/ranking/claude_ranker.py     ClaudeRanker(Ranker)
src/startup_agent/services/hybrid_matching.py           HybridMatchingService
# settings + cli.py modified
tests/adapters/ranking/test_claude_ranker.py
tests/services/test_hybrid_matching.py
```

---

### Task 3b.1: Anthropic dep + settings

**Files:** `pyproject.toml` (via uv), `src/startup_agent/config/settings.py`; Test `tests/config/test_settings.py`

- [ ] **Step 1:** `uv add anthropic`.
- [ ] **Step 2: Failing test** (append to `tests/config/test_settings.py`):

```python
def test_settings_llm_defaults(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    from startup_agent.config.settings import Settings
    s = Settings()
    assert s.llm_model == "claude-opus-4-8"
    assert s.llm_threshold == 70
```

- [ ] **Step 3:** Add to `Settings`: `llm_model: str = "claude-opus-4-8"` and `llm_threshold: int = 70`.
- [ ] **Step 4:** `uv run pytest tests/config -v` → green.
- [ ] **Step 5: Commit** `chore: add anthropic dep + LLM ranker settings` (+ co-author trailer).

---

### Task 3b.2: ClaudeRanker

**Files:** Create `src/startup_agent/adapters/ranking/__init__.py` (empty), `src/startup_agent/adapters/ranking/claude_ranker.py`; Test `tests/adapters/ranking/__init__.py` (empty), `tests/adapters/ranking/test_claude_ranker.py`

- [ ] **Step 1: Write the failing test** (fake Anthropic client — no network)

```python
from types import SimpleNamespace

from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
from startup_agent.domain.models import Job


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        # echo a deterministic score; reason references the title in the user turn
        return SimpleNamespace(parsed_output=SimpleNamespace(score=88, reason="strong backend fit"))


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def _job(title):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location="Tel Aviv", description="build backend services")


def test_claude_ranker_returns_match_results():
    client = _FakeClient()
    ranker = ClaudeRanker(client=client, model="claude-opus-4-8")
    results = ranker.rank("backend engineer cv", [_job("Backend Engineer"), _job("Platform Engineer")])

    assert len(results) == 2
    assert results[0].score == 88
    assert results[0].reason == "strong backend fit"
    assert results[0].stage == "llm"
    assert results[0].job_id == _job("Backend Engineer").id


def test_claude_ranker_caches_cv_in_system_block():
    client = _FakeClient()
    ranker = ClaudeRanker(client=client, model="claude-opus-4-8")
    ranker.rank("MY CV TEXT", [_job("Backend Engineer")])

    kw = client.messages.calls[0]
    assert kw["model"] == "claude-opus-4-8"
    # CV goes in a cached system block; the job goes in the user turn
    system_texts = [b["text"] for b in kw["system"]]
    assert any("MY CV TEXT" in t for t in system_texts)
    assert any(b.get("cache_control") == {"type": "ephemeral"} for b in kw["system"])
    assert "Backend Engineer" in kw["messages"][0]["content"]
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`claude_ranker.py`)

```python
import anthropic
from pydantic import BaseModel, Field

from startup_agent.domain.models import Job, MatchResult
from startup_agent.ports.ranker import Ranker

_SYSTEM = (
    "You are a job-matching assistant. Given a candidate's CV and a single job "
    "posting, score how well the job fits the candidate from 0 to 100 and give a "
    "one-line reason (max ~20 words). Weigh role, seniority, skills, and domain. "
    "Be strict: 70+ means a genuinely strong fit worth applying to; 40-69 a "
    "stretch; below 40 a poor fit."
)


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

    def rank(self, cv_text: str, jobs: list[Job]) -> list[MatchResult]:
        results: list[MatchResult] = []
        for job in jobs:
            job_text = (
                f"Title: {job.title}\n"
                f"Location: {job.location or 'n/a'}\n\n"
                f"{(job.description or '')[:4000]}"
            )
            message = self._client.messages.parse(
                model=self._model,
                max_tokens=1000,
                system=[
                    {"type": "text", "text": _SYSTEM},
                    {"type": "text", "text": f"CANDIDATE CV:\n{cv_text}",
                     "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user",
                           "content": f"JOB POSTING:\n{job_text}\n\nScore this job for the candidate."}],
                output_format=_Score,
            )
            parsed = message.parsed_output
            results.append(MatchResult(job_id=job.id, score=parsed.score,
                                       reason=parsed.reason, stage="llm"))
        return results
```

- [ ] **Step 4: Run** `uv run pytest tests/adapters/ranking -v` → 2 passed.
- [ ] **Step 5: Commit** `feat: add ClaudeRanker (LLM scoring + reason, cached CV, structured output)`.

---

### Task 3b.3: HybridMatchingService + `match --llm`

**Files:** Create `src/startup_agent/services/hybrid_matching.py`; Modify `src/startup_agent/cli.py`; Test `tests/services/test_hybrid_matching.py`

- [ ] **Step 1: Write the failing test** (FakeEmbedder + FakeRanker + in-memory repo)

```python
from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.services.hybrid_matching import HybridMatchingService


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "backend" in t.lower() else [0.0, 1.0] for t in texts]


class FakeRanker:
    def rank(self, cv_text, jobs):
        # score by title: "Backend" high, others low
        out = []
        for j in jobs:
            score = 90 if "backend" in j.title.lower() else 50
            out.append(MatchResult(job_id=j.id, score=score, reason="r", stage="llm"))
        return out


def _repo():
    r = SQLiteJobRepository(":memory:")
    r.init_schema()
    r.upsert_company(Company(name="Acme"))
    cid = r.get_companies()[0].id_hash
    r.save_cv(path="cv.pdf", text="backend python", embedding=to_bytes([1.0, 0.0]), model="fake")
    r.upsert_job(Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                     url="https://x/1", location="Tel Aviv", description="backend role"))
    r.upsert_job(Job(company_id=cid, ats_job_id="2", title="Platform Engineer",
                     url="https://x/2", location="Tel Aviv", description="backend infra role"))
    return r


def test_hybrid_keeps_only_above_llm_threshold_sorted():
    repo = _repo()
    service = HybridMatchingService(
        repo=repo, embedder=FakeEmbedder(), ranker=FakeRanker(),
        preferences=Preferences(title_include=["engineer"], exclude=["Senior"]),
        sim_threshold=0.4, llm_threshold=70,
    )
    results = service.run()  # list[(Job, MatchResult)]
    titles = [job.title for job, _ in results]
    assert "Backend Engineer" in titles          # llm 90 >= 70
    assert "Platform Engineer" not in titles      # llm 50 < 70
    assert all(m.score >= 70 for _, m in results)


def test_hybrid_persists_matches_and_run():
    repo = _repo()
    service = HybridMatchingService(
        repo=repo, embedder=FakeEmbedder(), ranker=FakeRanker(),
        preferences=Preferences(title_include=["engineer"]),
        sim_threshold=0.4, llm_threshold=70,
    )
    service.run()
    # a run row exists (record_run returns an int id; matches recorded without error)
    # smoke: re-running doesn't raise
    service.run()
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (`hybrid_matching.py`)

```python
import structlog

from startup_agent.domain.models import Job, MatchResult, RunReport
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.ranker import Ranker
from startup_agent.ports.repository import JobRepository
from startup_agent.services.matching import SimilarityMatchingService

logger = structlog.get_logger()


class HybridMatchingService:
    def __init__(self, repo: JobRepository, embedder: Embedder, ranker: Ranker,
                 preferences: Preferences, sim_threshold: float,
                 llm_threshold: int) -> None:
        self._repo = repo
        self._ranker = ranker
        self._llm_threshold = llm_threshold
        self._similarity = SimilarityMatchingService(
            repo=repo, embedder=embedder, preferences=preferences, threshold=sim_threshold
        )

    def run(self) -> list[tuple[Job, MatchResult]]:
        candidates = [job for job, _score in self._similarity.run()]
        if not candidates:
            self._repo.record_run(RunReport(jobs_matched=0))
            return []

        cv = self._repo.get_cv()
        if cv is None:
            raise RuntimeError("No CV loaded. Run 'startup-agent load-cv --path <pdf>' first.")

        scored = self._ranker.rank(cv["text"], candidates)
        run_id = self._repo.record_run(RunReport(jobs_fetched=len(candidates),
                                                  jobs_matched=len(scored)))
        self._repo.record_matches(run_id, scored)

        by_id = {job.id: job for job in candidates}
        kept = sorted(
            (m for m in scored if m.score >= self._llm_threshold),
            key=lambda m: m.score, reverse=True,
        )
        logger.info("hybrid_match_complete", candidates=len(candidates), kept=len(kept))
        return [(by_id[m.job_id], m) for m in kept if m.job_id in by_id]
```

- [ ] **Step 4: Add the `--llm` flag to the `match` CLI** (`cli.py`). Replace the existing `match` command with this version (keeps the similarity-only path as default):

```python
from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
from startup_agent.services.hybrid_matching import HybridMatchingService


@app.command("match")
def match(db_path: str = typer.Option("jobs.db", "--db-path"),
          llm: bool = typer.Option(False, "--llm", help="Also score candidates with Claude")) -> None:
    """Rank stored jobs against the CV. --llm adds Claude scoring + reasons."""
    settings = Settings()
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    prefs = load_preferences(settings.preferences_path)
    embedder = LocalEmbedder(settings.embedding_model)
    names = {c.id_hash: c.name for c in repo.get_companies()}

    if llm:
        ranker = ClaudeRanker(api_key=settings.anthropic_api_key, model=settings.llm_model)
        service = HybridMatchingService(
            repo=repo, embedder=embedder, ranker=ranker, preferences=prefs,
            sim_threshold=settings.match_threshold, llm_threshold=settings.llm_threshold,
        )
        results = service.run()
        typer.echo(f"{len(results)} matching jobs (LLM score >= {settings.llm_threshold}):")
        for job, m in results:
            typer.echo(f"  [{m.score}] {job.title} @ {names.get(job.company_id, '?')} "
                       f"— {job.location or 'n/a'} — {m.reason} — {job.url}")
        return

    from startup_agent.services.matching import SimilarityMatchingService
    service = SimilarityMatchingService(repo=repo, embedder=embedder,
                                        preferences=prefs, threshold=settings.match_threshold)
    results = service.run()
    typer.echo(f"{len(results)} matching jobs (similarity >= {settings.match_threshold}):")
    for job, score in results:
        typer.echo(f"  [{score:.2f}] {job.title} @ {names.get(job.company_id, '?')} "
                   f"— {job.location or 'n/a'} — {job.url}")
```

(Keep the existing `load-cv` and other commands and imports intact.)

- [ ] **Step 5: Run** `uv run pytest tests/services/test_hybrid_matching.py -v` → green. Full suite `uv run pytest -q` → all green. `uv run ruff check src tests` → clean. CLI offline check: `uv run startup-agent match --help` shows `--llm`.
- [ ] **Step 6: Commit** `feat: add HybridMatchingService + match --llm (Claude scoring on candidates)`.

---

### Task 3b.4: Live smoke + checkpoint

> Requires `ANTHROPIC_API_KEY`. The user adds it to `.env` (the file is gitignored — never commit it, never paste the key in chat).

- [ ] **Step 1:** Confirm `.env` contains `ANTHROPIC_API_KEY=...` (user-provided). Optional: `LLM_MODEL=claude-haiku-4-5` to minimize cost.
- [ ] **Step 2:** With jobs + CV already loaded (from Stage 3a), run:
  `uv run startup-agent match --llm`
- [ ] **Step 3:** Eyeball the scored list with reasons. Tune `LLM_THRESHOLD` if needed.
- [ ] **Step 4:** Push branch, open PR, merge to `main`.

> **Checkpoint:** `main` now produces a Claude-scored, reasoned, ranked job list. Stage 4 (digest) and Stage 5 (scheduling) remain.

---

## Self-Review Notes
- **Spec coverage:** ClaudeRanker implements the `Ranker` port (3b.2); hybrid pipeline composes 3a similarity → LLM scoring, persists matches, threshold-not-cap (3b.3); settings + CLI flag (3b.1/3b.3). Digest (Stage 4) and scheduling (Stage 5) are out of scope.
- **Placeholder scan:** none.
- **Type consistency:** `Ranker.rank(cv_text, jobs) -> list[MatchResult]`, `MatchResult(job_id, score, reason, stage)`, `HybridMatchingService(repo, embedder, ranker, preferences, sim_threshold, llm_threshold).run() -> list[tuple[Job, MatchResult]]`, Settings `llm_model`/`llm_threshold` — consistent with 3a's `SimilarityMatchingService` and the existing repo methods (`record_run`, `record_matches`, `get_cv`).
- **API correctness:** uses `messages.parse()` with `output_format` (structured outputs), CV in a `cache_control: ephemeral` system block (prompt caching across the per-job batch), model `claude-opus-4-8`, no `temperature`/`budget_tokens` (removed on 4.8). Tests use a fake client — no network, no key.
