# Matching Rerank + Experience-Fit Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw-cosine fit scores with a recall→rerank model: embeddings find candidates, a precomputed per-job "rank card" + gpt-4o-mini produce a calibrated 0–100 skills score, and code applies a deterministic asymmetric experience-gap penalty.

**Architecture:** Batch precomputes per job: embedding (exists) + a structured **rank card** (new). Search does cheap cosine recall, picks candidates (top 25 ∪ posted-last-24h), LLM-scores each from its rank card (cached per user+job, capped), then applies experience/max_years penalties in code and maps to tiers (Strong 70+/Stretch 40–69/Weak <40).

**Tech Stack:** Python 3.13, uv, pytest, FastAPI, Postgres (psycopg3), OpenAI (`openai`), React/Vite/TS.

**Spec:** `docs/specs/2026-06-21-matching-rerank-scoring-redesign.md`

**Branch:** work on `cloud-5/deploy`. Postgres tests use the local docker container and `pytest.importorskip`/skip if unreachable; do NOT run multiple pytest processes against it concurrently.

---

### Task 1: Capture user's years of experience

**Files:**
- Modify: `src/startup_agent/domain/applicant_profile.py`
- Modify: `src/startup_agent/adapters/profiling/prompt.py`
- Test: `tests/adapters/profiling/test_prompt.py`

- [ ] **Step 1: Write the failing test** — append to `tests/adapters/profiling/test_prompt.py`:

```python
def test_to_profile_extracts_years_experience():
    from startup_agent.adapters.profiling.prompt import to_profile
    p = to_profile({"first_name": "A", "years_experience": 4})
    assert p.years_experience == 4

def test_to_profile_years_none_when_absent_or_unparseable():
    from startup_agent.adapters.profiling.prompt import to_profile
    assert to_profile({"first_name": "A"}).years_experience is None
    assert to_profile({"years_experience": "lots"}).years_experience is None
```

- [ ] **Step 2: Run — expect FAIL**

Run: `uv run pytest tests/adapters/profiling/test_prompt.py -q`
Expected: FAIL (`years_experience` not a field / not parsed).

- [ ] **Step 3: Add the field.** In `src/startup_agent/domain/applicant_profile.py`, inside `ApplicantProfile`, add after `current_title`:

```python
    current_title: str = ""
    years_experience: int | None = None
```

- [ ] **Step 4: Extract it.** Replace the body of `src/startup_agent/adapters/profiling/prompt.py` with:

```python
from startup_agent.domain.applicant_profile import ApplicantProfile

INSTRUCTIONS = (
    "You read a candidate's CV and extract ONLY these fields: "
    "first_name, last_name, location (city, country), current_title "
    "(their most recent or current job title), and years_experience "
    "(their total years of professional experience as a whole number; null if unclear). "
    "Do NOT extract email, phone, or URLs. "
    'Return JSON: {"first_name": "", "last_name": "", "location": "", '
    '"current_title": "", "years_experience": null}.'
)

_TEXT_FIELDS = ("first_name", "last_name", "location", "current_title")


def to_profile(data: dict) -> ApplicantProfile:
    """Build an ApplicantProfile holding ONLY the LLM judgment fields."""
    fields = {k: str(data.get(k) or "") for k in _TEXT_FIELDS}
    years = data.get("years_experience")
    fields["years_experience"] = years if isinstance(years, int) and years >= 0 else None
    return ApplicantProfile(**fields)
```

- [ ] **Step 5: Run — expect PASS**, then commit.

Run: `uv run pytest tests/adapters/profiling/test_prompt.py -q`  → PASS
```bash
git add src/startup_agent/domain/applicant_profile.py src/startup_agent/adapters/profiling/prompt.py tests/adapters/profiling/test_prompt.py
git commit -m "feat(scoring): extract candidate years_experience from CV"
```

---

### Task 2: Experience-gap penalty (deterministic bands)

**Files:**
- Create: `src/startup_agent/matching/experience_fit.py`
- Test: `tests/matching/test_experience_fit.py`

- [ ] **Step 1: Write the failing test** — create `tests/matching/test_experience_fit.py`:

```python
import pytest
from startup_agent.matching.experience_fit import experience_penalty

@pytest.mark.parametrize("user,required,expected", [
    (5, 5, 0), (5, 6, 0),          # 0-1 under -> none
    (3, 5, 15), (3, 6, 15),        # 2-3 under -> 15
    (2, 6, 30), (1, 6, 30),        # 4-5 under -> 30
    (1, 7, 50), (0, 10, 50),       # 6+ under -> 50
    (6, 5, 0), (6, 4, 0),          # 0-2 over -> none
    (8, 4, 5), (8, 3, 5),          # 3-5 over -> 5
    (10, 2, 12), (12, 1, 12),      # 6+ over -> 12
])
def test_experience_penalty_bands(user, required, expected):
    assert experience_penalty(user, required) == expected

def test_experience_penalty_none_inputs_are_neutral():
    assert experience_penalty(None, 5) == 0
    assert experience_penalty(5, None) == 0
    assert experience_penalty(None, None) == 0
```

- [ ] **Step 2: Run — expect FAIL** (`uv run pytest tests/matching/test_experience_fit.py -q`): module missing.

- [ ] **Step 3: Implement** — create `src/startup_agent/matching/experience_fit.py`:

```python
def experience_penalty(user_years: int | None, required_years: int | None) -> int:
    """Points to subtract from a 0-100 fit score for an experience mismatch.

    Asymmetric: under-qualification (job needs more than the candidate has) is a
    far bigger barrier than over-qualification. Returns 0 when either side is unknown.
    """
    if user_years is None or required_years is None:
        return 0
    gap = required_years - user_years  # >0 underqualified, <0 overqualified
    if gap >= 6:
        return 50
    if gap >= 4:
        return 30
    if gap >= 2:
        return 15
    if gap >= -2:        # -2..1 → well matched / trivial stretch
        return 0
    if gap >= -5:        # 3-5 years over
        return 5
    return 12            # 6+ years over
```

- [ ] **Step 4: Run — expect PASS**, then commit.

Run: `uv run pytest tests/matching/test_experience_fit.py -q` → PASS
```bash
git add src/startup_agent/matching/experience_fit.py tests/matching/test_experience_fit.py
git commit -m "feat(scoring): asymmetric experience-gap penalty"
```

---

### Task 3: Infer a job's required years (regex + seniority title fallback)

**Files:**
- Modify: `src/startup_agent/matching/experience.py`
- Test: `tests/matching/test_experience.py`

- [ ] **Step 1: Write the failing test** — append to `tests/matching/test_experience.py`:

```python
def test_inferred_required_years_prefers_explicit_card_then_regex_then_title():
    from startup_agent.matching.experience import inferred_required_years
    # explicit card value wins
    assert inferred_required_years("Backend Engineer", "needs 4 years", card_years=7) == 7
    # regex from description
    assert inferred_required_years("Backend Engineer", "5+ years required") == 5
    # title fallback when nothing stated
    assert inferred_required_years("Senior Backend Engineer", "great team") == 6
    assert inferred_required_years("Junior Developer", "great team") == 1
    assert inferred_required_years("Staff Engineer", None) == 8
    assert inferred_required_years("Backend Engineer", None) == 3   # no marker -> mid
```

- [ ] **Step 2: Run — expect FAIL** (`uv run pytest tests/matching/test_experience.py -q`).

- [ ] **Step 3: Implement** — append to `src/startup_agent/matching/experience.py`:

```python
_SENIORITY_YEARS = (
    ("director", 10), ("principal", 8), ("staff", 8), ("lead", 8),
    ("senior", 6), ("sr.", 6), ("junior", 1), ("entry", 1),
    ("associate", 1), ("intern", 0),
)


def years_from_title(title: str) -> int:
    t = title.lower()
    for marker, years in _SENIORITY_YEARS:
        if marker in t:
            return years
    return 3  # no seniority marker -> assume mid-level


def inferred_required_years(title: str, description: str | None,
                            card_years: int | None = None) -> int | None:
    """Best estimate of a job's required years: explicit card value, then a number
    parsed from the description, then an inference from the title's seniority."""
    if card_years is not None:
        return card_years
    parsed = required_years(description)
    if parsed is not None:
        return parsed
    return years_from_title(title)
```

- [ ] **Step 4: Run — expect PASS**, then commit.
```bash
git add src/startup_agent/matching/experience.py tests/matching/test_experience.py
git commit -m "feat(scoring): infer required years from card/regex/title"
```

---

### Task 4: Rank-card storage (schema + repo methods)

**Files:**
- Modify: `src/startup_agent/adapters/storage/pg_schema.sql`
- Modify: `src/startup_agent/adapters/storage/postgres_repository.py`
- Test: `tests/adapters/storage/test_rank_card.py`

- [ ] **Step 1: Add the column.** In `pg_schema.sql`, in the `jobs` table add a column (alongside `embedding`/`embed_model`):

```sql
    rank_card       JSONB,
```
Also add an idempotent migration line near the other `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements (match the file's existing pattern):
```sql
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS rank_card JSONB;
```

- [ ] **Step 2: Write the failing test** — create `tests/adapters/storage/test_rank_card.py`:

```python
import os
import pytest

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")
from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
from startup_agent.domain.models import AtsType, Company, Job


@pytest.fixture
def repo():
    try:
        psycopg.connect(DSN).close()
    except Exception:
        pytest.skip("no test Postgres reachable")
    r = PostgresJobRepository(DSN); r.init_schema()
    r._conn.execute("TRUNCATE matches, runs, jobs, companies RESTART IDENTITY CASCADE")
    return r


def test_store_and_read_rank_card(repo):
    cid = repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="a"))
    j = Job(company_id=cid, ats_job_id="1", title="Backend Eng", url="u",
            description="Go and k8s", location="Tel Aviv")
    repo.upsert_job(j)
    assert [jid for jid, _, _ in repo.jobs_needing_rank_card()] == [j.id]   # needs one
    card = {"tech_stack": ["Go"], "required_years": 5, "seniority": "senior"}
    repo.store_rank_card(j.id, card)
    assert repo.get_rank_card(j.id) == card
    assert repo.jobs_needing_rank_card() == []                              # now satisfied
```

- [ ] **Step 3: Run — expect FAIL** (`uv run pytest tests/adapters/storage/test_rank_card.py -q`): methods missing.

- [ ] **Step 4: Implement** — in `postgres_repository.py`, add these methods near `store_embedding` (note `Jsonb` import — match how the file already imports psycopg types; if not present add `from psycopg.types.json import Jsonb` at the top):

```python
    def jobs_needing_rank_card(self) -> list[tuple[str, str, str]]:
        """Active jobs with no rank card → (id, title, description)."""
        rows = self._conn.execute(
            "SELECT id, title, description FROM jobs "
            "WHERE active = TRUE AND rank_card IS NULL"
        ).fetchall()
        return [(r["id"], r["title"], r["description"] or "") for r in rows]

    def store_rank_card(self, job_id: str, card: dict) -> None:
        self._conn.execute("UPDATE jobs SET rank_card=%s WHERE id=%s",
                           (Jsonb(card), job_id))
        self._conn.commit()

    def get_rank_card(self, job_id: str) -> dict | None:
        r = self._conn.execute("SELECT rank_card FROM jobs WHERE id=%s", (job_id,)).fetchone()
        return r["rank_card"] if r and r["rank_card"] is not None else None
```

- [ ] **Step 5: Run — expect PASS**, then commit.
```bash
git add src/startup_agent/adapters/storage/pg_schema.sql src/startup_agent/adapters/storage/postgres_repository.py tests/adapters/storage/test_rank_card.py
git commit -m "feat(scoring): rank_card column + repo store/read/needs methods"
```

---

### Task 5: Rank-card extractor adapter (gpt-4o-mini)

**Files:**
- Create: `src/startup_agent/adapters/summarizing/__init__.py` (empty)
- Create: `src/startup_agent/adapters/summarizing/prompt.py`
- Create: `src/startup_agent/adapters/summarizing/openai_summarizer.py`
- Test: `tests/adapters/summarizing/test_openai_summarizer.py` (+ `__init__.py`)

- [ ] **Step 1: Write the failing test** — create `tests/adapters/summarizing/test_openai_summarizer.py`:

```python
import json
from startup_agent.adapters.summarizing.openai_summarizer import OpenAIJobSummarizer


class _Msg:
    def __init__(self, content): self.message = type("M", (), {"content": content})
class _Resp:
    def __init__(self, content): self.choices = [_Msg(content)]
class _Completions:
    def __init__(self): self.calls = []
    def create(self, model, response_format, messages):
        self.calls.append((model, messages))
        return _Resp(json.dumps({"tech_stack": ["Go"], "required_years": 5,
                                 "seniority": "senior", "role_domain": "backend",
                                 "must_haves": [], "domain_industry": "fintech",
                                 "summary": "Senior Go backend."}))
class _Client:
    def __init__(self): self.chat = type("C", (), {"completions": _Completions()})()


def test_summarize_returns_structured_card_with_chosen_model():
    client = _Client()
    s = OpenAIJobSummarizer(model="gpt-4o-mini", client=client)
    card = s.summarize("Senior Backend Engineer", "Go, k8s, 5 years")
    assert card["required_years"] == 5 and card["role_domain"] == "backend"
    assert client.chat.completions.calls[0][0] == "gpt-4o-mini"
```

- [ ] **Step 2: Run — expect FAIL** (`uv run pytest tests/adapters/summarizing/test_openai_summarizer.py -q`).

- [ ] **Step 3: Implement prompt** — create `src/startup_agent/adapters/summarizing/prompt.py`:

```python
INSTRUCTIONS = (
    "You read ONE job posting and extract a compact structured card a downstream "
    "ranker will use. Return JSON with exactly these keys: "
    '{"tech_stack": [..languages/frameworks/tools..], '
    '"required_years": <int or null - lowest years of experience required>, '
    '"seniority": "junior|mid|senior|staff|principal|director|unknown", '
    '"role_domain": "backend|frontend|full-stack|data|ai|devops|security|other", '
    '"must_haves": [..hard requirements e.g. "fluent Hebrew", a clearance, a degree..], '
    '"domain_industry": "<e.g. fintech, cybersecurity, healthtech, or empty>", '
    '"summary": "<=2 sentences on the role essence"}. '
    "Base everything ONLY on the posting. Use null/empty when unknown."
)
```

- [ ] **Step 4: Implement adapter** — create `src/startup_agent/adapters/summarizing/openai_summarizer.py`:

```python
import json

from startup_agent.adapters.summarizing.prompt import INSTRUCTIONS

_KEYS = ("tech_stack", "required_years", "seniority", "role_domain",
         "must_haves", "domain_industry", "summary")


class OpenAIJobSummarizer:
    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini",
                 base_url: str = "", client: object | None = None) -> None:
        self._api_key, self._base_url, self._model = api_key, base_url, model
        self._client = client

    def _ensure(self):
        if self._client is None:
            from openai import OpenAI
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def summarize(self, title: str, description: str) -> dict:
        resp = self._ensure().chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"TITLE: {title}\n\nPOSTING:\n{description[:4000]}"},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return {k: data.get(k) for k in _KEYS}
```

- [ ] **Step 5: Run — expect PASS**, then commit.
```bash
git add src/startup_agent/adapters/summarizing/ tests/adapters/summarizing/
git commit -m "feat(scoring): OpenAI job rank-card summarizer (gpt-4o-mini)"
```

---

### Task 6: Batch builds rank cards (incremental, shared)

**Files:**
- Modify: `src/startup_agent/companies/batch.py`
- Modify: `src/startup_agent/cli.py` (batch command)
- Modify: `src/startup_agent/config/settings.py` (rerank/summarizer model)
- Test: `tests/companies/test_batch.py`

- [ ] **Step 1: Add settings.** In `settings.py`, after `openai_embedding_model`, add:

```python
    llm_rerank_model: str = "gpt-4o-mini"
```
and change the cap default:
```python
    llm_daily_cap: int = 60             # per-user LLM calls/day
```

- [ ] **Step 2: Write the failing test** — append to `tests/companies/test_batch.py`:

```python
class _FakeSummarizer:
    def __init__(self): self.calls = 0
    def summarize(self, title, description):
        self.calls += 1
        return {"tech_stack": ["Go"], "required_years": 4, "seniority": "mid",
                "role_domain": "backend", "must_haves": [], "domain_industry": "",
                "summary": "mid backend"}


def test_batch_builds_rank_cards_incrementally(repo):
    cid = repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="a"))
    j1 = Job(company_id=cid, ats_job_id="1", title="Backend Eng", url="u",
             description="go", location="Tel Aviv")
    summ = _FakeSummarizer()
    r1 = run_batch(repo, _FakeFactory([j1]), _FakeEmbedder(), model="bge",
                   summarizer=summ)
    assert r1["carded"] == 1 and summ.calls == 1
    assert repo.get_rank_card(j1.id)["required_years"] == 4
    # second run: card already present -> not rebuilt
    r2 = run_batch(repo, _FakeFactory([j1]), _FakeEmbedder(), model="bge",
                   summarizer=summ)
    assert r2["carded"] == 0 and summ.calls == 1
```

- [ ] **Step 3: Run — expect FAIL** (`uv run pytest tests/companies/test_batch.py::test_batch_builds_rank_cards_incrementally -q`).

- [ ] **Step 4: Implement.** In `src/startup_agent/companies/batch.py`, update the signature and add a carding step after embedding (step 2). New signature:

```python
def run_batch(repo, factory, embedder, *, model: str,
              seed_path: str | None = None, progress=None, summarizer=None) -> dict:
```
After the embedding block (before retire), add:
```python
    # 2b. build rank cards for jobs that lack one (incremental, shared across users)
    carded = 0
    if summarizer is not None:
        for job_id, title, description in repo.jobs_needing_rank_card():
            try:
                repo.store_rank_card(job_id, summarizer.summarize(title, description))
                carded += 1
            except Exception as error:  # noqa: BLE001 - one bad job shouldn't abort
                logger.warning("rank_card_failed", job_id=job_id, error=str(error))
```
Add `"carded": carded` to the returned `result` dict.

- [ ] **Step 5: Run — expect PASS** (`uv run pytest tests/companies/test_batch.py -q`).

- [ ] **Step 6: Wire the CLI.** In `src/startup_agent/cli.py` `batch` command, after building `embedder`, add:

```python
    from startup_agent.adapters.summarizing.openai_summarizer import OpenAIJobSummarizer
    summarizer = OpenAIJobSummarizer(api_key=settings.openai_api_key,
                                     model=settings.llm_rerank_model,
                                     base_url=settings.openai_base_url)
```
and pass `summarizer=summarizer` into `run_batch(...)`.

- [ ] **Step 7: Run full suite (env aside if present), commit.**
```bash
[ -f .env ] && mv .env .env.off; uv run pytest -q; [ -f .env.off ] && mv .env.off .env
git add src/startup_agent/companies/batch.py src/startup_agent/cli.py src/startup_agent/config/settings.py tests/companies/test_batch.py
git commit -m "feat(scoring): batch builds per-job rank cards; cap 60; rerank model"
```

---

### Task 7: Ranker uses the rank card + new criteria + district fact

**Files:**
- Modify: `src/startup_agent/adapters/ranking/prompt.py`
- Test: `tests/adapters/ranking/test_prompt.py`

- [ ] **Step 1: Write the failing test** — append to `tests/adapters/ranking/test_prompt.py` (create if absent, with imports):

```python
def test_job_text_uses_rank_card_and_district_when_present():
    from startup_agent.adapters.ranking.prompt import job_text
    from startup_agent.domain.models import Job
    job = Job(company_id="c", ats_job_id="1", title="Backend Eng", url="u",
              location="Tel Aviv", description="LONG DESCRIPTION " * 500)
    card = {"tech_stack": ["Go"], "role_domain": "backend", "summary": "Go backend",
            "must_haves": ["Hebrew"], "domain_industry": "fintech"}
    text = job_text(job, card=card, district="center")
    assert "Go" in text and "center" in text and "fintech" in text
    assert len(text) < 1000          # card is compact, not the 4000-char description

def test_instructions_tell_model_to_ignore_seniority_years():
    from startup_agent.adapters.ranking.prompt import INSTRUCTIONS
    low = INSTRUCTIONS.lower()
    assert "ignore" in low and ("seniority" in low or "years" in low)
```

- [ ] **Step 2: Run — expect FAIL** (`uv run pytest tests/adapters/ranking/test_prompt.py -q`).

- [ ] **Step 3: Implement.** Replace `INSTRUCTIONS` and `job_text` in `src/startup_agent/adapters/ranking/prompt.py` with:

```python
INSTRUCTIONS = (
    "You are a job-matching assistant. Given a candidate's CV and a single job's "
    "summary card, score how well the job fits the candidate's SKILLS and ROLE from "
    "0 to 100, and give a one-line reason (max ~20 words). "
    "Weigh: tech-stack overlap (high), role/domain alignment (high), must-have "
    "requirements met (medium-high), domain/industry match and skill recency (medium). "
    "IGNORE experience level, seniority, years, and location — those are handled "
    "separately; do not raise or lower the score for them. "
    "Be strict: 70+ a genuinely strong skills fit; 40-69 a stretch; below 40 poor."
)
```
(Keep `preferences_clause` as-is.) Replace `job_text`:
```python
def job_text(job, card: dict | None = None, district: str | None = None) -> str:
    loc = f"Location district: {district} (already validated — do not score location).\n" \
        if district else ""
    if card:
        import json
        return f"Title: {job.title}\n{loc}\nJob card (use this):\n{json.dumps(card)}"
    return f"Title: {job.title}\n{loc}\n{(job.description or '')[:4000]}"
```

- [ ] **Step 4: Run — expect PASS**, commit.
```bash
git add src/startup_agent/adapters/ranking/prompt.py tests/adapters/ranking/test_prompt.py
git commit -m "feat(scoring): ranker scores skills only from rank card; ignore level/location"
```

---

### Task 8: Make the ranker accept card + district per job

**Files:**
- Modify: `src/startup_agent/adapters/ranking/openai_ranker.py`
- Modify: `src/startup_agent/ports/ranker.py` (signature note only if it declares `rank`)
- Test: `tests/adapters/ranking/test_openai_ranker.py`

- [ ] **Step 1: Write the failing test** — append to `tests/adapters/ranking/test_openai_ranker.py`:

```python
def test_rank_one_passes_card_and_district_into_prompt():
    import json
    from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
    from startup_agent.domain.models import Job
    captured = {}
    class _Comp:
        def create(self, model, response_format, messages):
            captured["user"] = messages[-1]["content"]
            class R:
                choices = [type("c", (), {"message": type("m", (), {"content": json.dumps({"score": 80, "reason": "good"})})})]
            return R()
    class _Client: chat = type("C", (), {"completions": _Comp()})()
    r = OpenAIRanker(model="gpt-4o-mini", client=_Client())
    job = Job(company_id="c", ats_job_id="1", title="Backend Eng", url="u", location="Tel Aviv")
    out = r.rank_one("CV", job, card={"tech_stack": ["Go"]}, district="center")
    assert out.score == 80
    assert "Go" in captured["user"] and "center" in captured["user"]
```

- [ ] **Step 2: Run — expect FAIL**.

- [ ] **Step 3: Implement.** In `openai_ranker.py`, add a `rank_one` method (keep `rank` for back-compat by delegating). Replace the per-job loop body to use `job_text(job, card, district)`:

```python
    def rank_one(self, cv_text, job, preferences=None, card=None, district=None):
        instructions = INSTRUCTIONS
        clause = preferences_clause(preferences)
        if clause:
            instructions = f"{INSTRUCTIONS}\n\n{clause}"
        instructions += '\n\nRespond ONLY with JSON: {"score": <int 0-100>, "reason": "<one line>"}'
        completion = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user",
                 "content": f"CANDIDATE CV:\n{cv_text}\n\nJOB:\n{job_text(job, card, district)}\n\nScore this job."},
            ],
        )
        data = json.loads(completion.choices[0].message.content)
        score = max(0, min(100, int(data.get("score", 0))))
        return MatchResult(job_id=job.id, score=score,
                           reason=str(data.get("reason", "")), stage="llm")

    def rank(self, cv_text, jobs, preferences=None):
        return [self.rank_one(cv_text, j, preferences) for j in jobs]
```

- [ ] **Step 4: Run — expect PASS**, commit.
```bash
git add src/startup_agent/adapters/ranking/openai_ranker.py tests/adapters/ranking/test_openai_ranker.py
git commit -m "feat(scoring): ranker.rank_one(card, district)"
```

---

### Task 9: Drop the max-years hard filter

**Files:**
- Modify: `src/startup_agent/matching/prefilter.py`
- Test: `tests/matching/test_prefilter.py`

- [ ] **Step 1: Update the failing test** — in `tests/matching/test_prefilter.py`, find the test asserting max_years drops a job and change it to assert it now PASSES the prefilter (add a clear new test):

```python
def test_max_years_no_longer_hard_filters():
    from startup_agent.matching.prefilter import passes_prefilter
    from startup_agent.domain.models import Job
    from startup_agent.domain.preferences import Preferences
    job = Job(company_id="c", ats_job_id="1", title="Engineer", url="u",
              location="Tel Aviv", description="requires 10 years of experience")
    assert passes_prefilter(job, Preferences(max_years=3, districts=["center"])) is True
```

- [ ] **Step 2: Run — expect FAIL** (old behavior drops it).

- [ ] **Step 3: Implement.** In `prefilter.py`, delete the block:
```python
    # max experience years (drop only when the job states MORE than allowed)
    if preferences.max_years is not None:
        needed = required_years(job.description)
        if needed is not None and needed > preferences.max_years:
            return False
```
and remove the now-unused `from startup_agent.matching.experience import required_years` import.

- [ ] **Step 4: Run — expect PASS** (whole prefilter file): `uv run pytest tests/matching/test_prefilter.py -q`. Fix any other test that assumed the drop. Commit.
```bash
git add src/startup_agent/matching/prefilter.py tests/matching/test_prefilter.py
git commit -m "refactor(scoring): max_years is a soft signal, not a hard filter"
```

---

### Task 10: Rewrite `match_for_user` — candidates, card rerank, penalties, tiers, ai_scored

**Files:**
- Modify: `api/schemas.py` (add `ai_scored`, helper for tier)
- Modify: `src/startup_agent/services/cloud_match.py`
- Modify: `api/routes/results.py` (pass rerank model + user years)
- Test: `tests/services/test_cloud_match.py`

- [ ] **Step 1: Add `ai_scored` to JobMatch.** In `api/schemas.py` `JobMatch`, add `ai_scored: bool = False`. In `to_job_match(...)` set `ai_scored=False`; in `job_match_from_result(...)` set `ai_scored=True`.

- [ ] **Step 2: Write the failing test** — replace the body of `tests/services/test_cloud_match.py` scoring test (or add) with one that drives the new behavior. It uses fakes; no network:

```python
def test_experience_penalty_demotes_over_level_job(monkeypatch):
    # two jobs, identical LLM skill score 80; one needs 6 yrs more than the user.
    # the over-level one must end up lower after the code penalty.
    ...  # construct fake scoped_repo/user_repo/ranker per existing test fakes in this file,
         # set applicant_profile years_experience=2, job A required_years=2, job B required_years=8,
         # ranker returns score 80 for both -> assert final A.score (80) > B.score (<=50)
```
(Engineer: mirror the existing fakes already in `test_cloud_match.py`; assert the over-level job's final score is `80 - 50 = 30` → tier "Weak", and the on-level job stays 80 → "Strong".)

- [ ] **Step 3: Run — expect FAIL**.

- [ ] **Step 4: Implement** — rewrite `match_for_user` in `cloud_match.py`. Key changes (keep the existing prefs/companies/usage setup and the `_load_prefs` import):

```python
from startup_agent.matching.experience import inferred_required_years
from startup_agent.matching.experience_fit import experience_penalty

def _tier_ok(final: int) -> int:
    return max(0, min(100, final))

def match_for_user(scoped_repo, user_repo, user_id, embedder, preferences_path,
                   threshold, *, ranker=None, cap=60, recent_hours=24, top_n=25,
                   now=None):
    from api.matching_view import _load_prefs
    prefs = _load_prefs(scoped_repo, preferences_path)
    pairs = SimilarityMatchingService(repo=scoped_repo, embedder=embedder,
                                      preferences=prefs, threshold=threshold).run()
    cv = scoped_repo.get_cv()
    cv_text = cv["text"] if cv else ""
    profile = scoped_repo.get_applicant_profile()       # ApplicantProfile or None
    user_years = profile.years_experience if profile else None
    companies = scoped_repo.get_companies()
    names = {c.id_hash: c.name for c in companies}
    links = {c.id_hash: c.linkedin_url for c in companies}
    sites = {c.id_hash: c.website for c in companies}
    now = now or datetime.now(timezone.utc)
    used = user_repo.get_llm_usage(user_id)

    # candidate set: top_n by cosine (pairs are already sorted desc by score) ∪ last-24h
    candidate_ids = {job.id for job, _ in pairs[:top_n]}
    candidate_ids |= {job.id for job, _ in pairs if _is_recent(job, now, recent_hours)}

    out = []
    for job, score in pairs:
        is_candidate = job.id in candidate_ids
        cached = user_repo.get_job_state(user_id, job.id)
        district = _district_name(job.location)         # see helper below
        if cached and cached.get("llm_score") is not None:
            base, reason, ai = cached["llm_score"], cached.get("llm_reason") or "", True
        elif is_candidate and ranker is not None and used < cap:
            try:
                card = scoped_repo.get_rank_card(job.id)
                r = ranker.rank_one(cv_text, job, prefs, card=card, district=district)
                user_repo.cache_llm_score(user_id, job.id, r.score, r.reason)
                used = user_repo.bump_llm_usage(user_id)
                base, reason, ai = r.score, r.reason, True
            except Exception as error:
                logger.warning("llm_rank_failed", job=job.title, error=str(error))
                base, reason, ai = int(score * 100), "", False
        else:
            base, reason, ai = int(score * 100), "", False

        if ai:
            card = scoped_repo.get_rank_card(job.id) or {}
            req = inferred_required_years(job.title, job.description,
                                          card.get("required_years"))
            penalty = experience_penalty(user_years, req)
            if prefs.max_years is not None and req is not None and req > prefs.max_years:
                penalty += 10
            final = _tier_ok(base - penalty)
            note = f" · needs ~{req} yrs vs your {user_years}" if penalty and user_years is not None else ""
            r = MatchResult(job_id=job.id, score=final, reason=(reason + note), stage="llm")
            jm = job_match_from_result(job, r, names, now, links, sites)
        else:
            jm = to_job_match(job, base / 100 if base <= 100 else base, names, now, links, sites)
        if cached and cached.get("status"):
            jm = jm.model_copy(update={"status": cached["status"]})
        out.append(jm)

    out.sort(key=lambda m: (m.ai_scored, m.score), reverse=True)   # AI-scored first, then by score
    user_repo.record_event(user_id, "search_run",
                           metadata={"matched": len(out), "llm_used_today": used})
    return out
```
Add the district helper at module top:
```python
from startup_agent.matching.location import classify_location, Region
_DNAME = {Region.CENTER: "center", Region.NORTH: "north", Region.SOUTH: "south",
          Region.JERUSALEM: "jerusalem"}
def _district_name(location):
    return _DNAME.get(classify_location(location))
```
> Note: `to_job_match` expects a 0-1 cosine; for unscored jobs pass the cosine `score` directly (it's already 0-1). Adjust the unscored branch to `to_job_match(job, score, ...)` and keep `base` only for the AI path. (Engineer: keep unscored math identical to today — `to_job_match(job, score, ...)`.)

- [ ] **Step 5: Verify `get_applicant_profile` exists on the scoped repo.** It must return an `ApplicantProfile`. If `UserScopedRepository` exposes `get_profile`, use that name instead — grep first: `grep -n "def get_profile\|def get_applicant_profile" src/startup_agent/adapters/storage/user_scoped.py src/startup_agent/adapters/storage/postgres_user_repository.py`. Use whichever exists; the spec's intent is "the user's stored applicant profile."

- [ ] **Step 6: Run — expect PASS** (`uv run pytest tests/services/test_cloud_match.py -q`).

- [ ] **Step 7: Wire the model.** In `api/routes/results.py`, where the cloud branch builds/【passes】 the ranker, ensure it uses the rerank model. In `api/deps.py` add:
```python
def get_rerank_ranker():
    from api.deps import build_ranker_from
    s = get_settings()
    return build_ranker_from("openai", s.openai_api_key, s.llm_rerank_model, s.openai_base_url)
```
and in `results.py` cloud branch call `match_for_user(..., ranker=get_rerank_ranker(), cap=settings.llm_daily_cap)`.

- [ ] **Step 8: Run full suite (env aside), commit.**
```bash
[ -f .env ] && mv .env .env.off; uv run pytest -q; [ -f .env.off ] && mv .env.off .env
git add api/schemas.py src/startup_agent/services/cloud_match.py api/routes/results.py api/deps.py tests/services/test_cloud_match.py
git commit -m "feat(scoring): recall->card rerank + experience penalty + tiers + ai_scored"
```

---

### Task 11: Frontend — tiers, "Stretch" label, ai_scored marker

**Files:**
- Modify: `frontend/src/api/client.ts` (add `ai_scored` to JobMatch)
- Modify: `frontend/src/components/JobCard.tsx` (matchTier thresholds)
- Modify: `frontend/src/styles/app.css` (tier-stretch + not-scored styles)

- [ ] **Step 1: Add the field.** In `frontend/src/api/client.ts` `JobMatch` interface, add `ai_scored: boolean;`.

- [ ] **Step 2: Update tiers.** In `frontend/src/components/JobCard.tsx`, replace `matchTier`:
```typescript
function matchTier(score: number): { label: string; cls: string } {
  if (score >= 70) return { label: "Strong", cls: "tier-strong" };
  if (score >= 40) return { label: "Stretch", cls: "tier-good" };
  return { label: "Weak", cls: "tier-weak" };
}
```
And where the score pill renders, when `!j.ai_scored` show a muted "~" prefix and title "Ranked by similarity, not AI-scored":
```tsx
<span className={`score-pill ${tier.cls}`} title={j.ai_scored ? "" : "Ranked by similarity, not AI-scored"}>
  {tier.label} · {j.ai_scored ? `✨${j.score}` : `~${j.score}`}
</span>
```

- [ ] **Step 3: CSS** — append to `frontend/src/styles/app.css`:
```css
.score-pill[title]:not([title=""]) { opacity: .85; }
```

- [ ] **Step 4: Build to verify TS compiles, commit.**
```bash
cd frontend && npm run build && cd ..
git add frontend/src/api/client.ts frontend/src/components/JobCard.tsx frontend/src/styles/app.css
git commit -m "feat(scoring): UI tiers Strong70/Stretch40/Weak + not-AI-scored marker"
```

---

### Task 12: Re-card existing jobs + manual batch run (data step)

**Files:** none (operational)

- [ ] **Step 1:** With `.env` holding `DATABASE_URL`, `OPENAI_API_KEY`, `EMBEDDING_PROVIDER=openai`, run the batch once so existing jobs get rank cards:
```bash
uv run startup-agent batch --seed data/companies.json
```
Expected: `carded: <N>` in the output for the ~460 jobs.

- [ ] **Step 2:** Verify cards exist:
```bash
uv run python -c "import psycopg; c=psycopg.connect(__import__('os').environ['DATABASE_URL']); print('carded:', c.execute('select count(*) from jobs where rank_card is not null').fetchone()[0])"
```

---

## Self-Review

**Spec coverage:** years extraction (T1), experience penalty bands (T2), inferred required years (T3), rank-card storage (T4) + extractor (T5) + batch build (T6), card-based skills-only ranker (T7,T8), drop max-years hard filter (T9), candidate set + penalties + tiers + ai_scored + cost cap (T10), UI tiers + marker (T11), backfill (T12). Geography fix → district passed in T7/T10. max_years soft −10 → T10. All spec sections covered.

**Placeholder note:** Task 10 Step 4's test body and Step 5/7 reference existing fakes/method names the engineer must confirm by grep (called out explicitly) — these are verification steps, not vague instructions. Everything else has complete code.

**Type consistency:** `rank_card` dict keys (`tech_stack`, `required_years`, `seniority`, `role_domain`, `must_haves`, `domain_industry`, `summary`) are identical across T5, T6, T7, T10. `experience_penalty(user_years, required_years)`, `inferred_required_years(title, description, card_years)`, `rank_one(cv_text, job, preferences, card, district)`, `ai_scored` are consistent across tasks.
