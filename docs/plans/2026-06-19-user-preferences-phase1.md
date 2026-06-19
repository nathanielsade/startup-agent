# Per-User Preferences — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the hardcoded global rules with a structured, user-editable preferences profile (stored in SQLite, edited in a new Preferences screen) that drives the filter + ranking pipeline — no API key required.

**Architecture:** Expand the `Preferences` domain model into structured fields; generalize the deterministic prefilter (hard drops) and add a soft-score adjuster (rank nudges); store prefs as JSON in SQLite; expose `GET/PUT /api/preferences`; add a React Preferences screen in the flow. Reuses ports-&-adapters layers; matching/CLI keep working.

**Tech Stack:** Python 3.13, pydantic v2, SQLite, FastAPI, React+Vite+TS. All Phase-1 work is offline-testable (no LLM, no key).

**Repo discipline:** Work ONLY in `/Users/netanelsade/projects/startup-agent`; never touch `/Users/netanelsade/conifers`. Branch `phase-7/user-preferences`. Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Scope note — what Phase 1 covers vs defers
**Implemented (data exists today):** Districts (multi), Remote, Max experience years, Posted-within-days (freshness), Title include/exclude (hard); Role/domain, Seniority (soft).
**Deferred (no backing data yet — needs a follow-up that persists `employment_type` on Job and a startup/enterprise tag on Company):** Employment type, Company type. These are omitted from the Phase-1 form and prefilter — do NOT build dead filters for them.

## File structure
```
src/startup_agent/domain/preferences.py        EXPAND: structured fields
src/startup_agent/matching/experience.py        NEW: required_years(description)
src/startup_agent/matching/location.py          MODIFY: region_allowed(location, districts, include_remote)
src/startup_agent/matching/prefilter.py          MODIFY: all hard rules from structured prefs
src/startup_agent/matching/soft_score.py          NEW: soft_adjust(job, prefs, base) -> float
src/startup_agent/services/matching.py            MODIFY: apply soft_adjust before sort
src/startup_agent/adapters/storage/schema.sql     ADD preferences table
src/startup_agent/adapters/storage/sqlite_repository.py  ADD save_preferences/get_preferences
api/routes/preferences.py                          NEW: GET/PUT /api/preferences
api/main.py                                        mount preferences router
api/deps.py / api/routes/run.py / results.py       use stored prefs (fallback to yaml seed)
frontend/src/api/client.ts                         add getPreferences/savePreferences + Preferences type
frontend/src/components/PreferencesForm.tsx        NEW
frontend/src/App.tsx                               add "preferences" phase in the flow
```

---

### Task 1: Expand the Preferences model

**Files:** Modify `src/startup_agent/domain/preferences.py`; Test `tests/domain/test_preferences.py` (append).

- [ ] **Step 1: Write the failing test**

```python
def test_structured_preference_fields_have_defaults():
    from startup_agent.domain.preferences import Preferences
    p = Preferences()
    assert p.districts == []
    assert p.include_remote is True
    assert p.max_years is None
    assert p.posted_within_days is None
    assert p.roles == []
    assert p.seniority == []
    assert p.title_include == []
    assert p.exclude == []


def test_preferences_accepts_structured_values():
    from startup_agent.domain.preferences import Preferences
    p = Preferences(districts=["center", "north"], include_remote=False,
                    max_years=3, posted_within_days=30,
                    roles=["backend", "ai"], seniority=["junior", "mid"],
                    title_include=["engineer"], exclude=["senior"])
    assert p.districts == ["center", "north"]
    assert p.max_years == 3
```

- [ ] **Step 2: Run** `uv run pytest tests/domain/test_preferences.py -v` → FAIL (no `districts`).
- [ ] **Step 3: Implement** — replace `src/startup_agent/domain/preferences.py`:

```python
from pydantic import BaseModel, Field


class Preferences(BaseModel):
    # hard filters
    districts: list[str] = Field(default_factory=list)        # center/north/south/jerusalem; [] = no constraint
    include_remote: bool = True
    max_years: int | None = None                              # None = no limit
    posted_within_days: int | None = None                     # None = no limit
    title_include: list[str] = Field(default_factory=list)    # title must contain one (if set)
    exclude: list[str] = Field(default_factory=list)          # title must not contain any
    # soft signals (rank only)
    roles: list[str] = Field(default_factory=list)            # domain keywords: backend/ai/data/...
    seniority: list[str] = Field(default_factory=list)        # junior/mid/senior
    # legacy/unused (kept for yaml-loader compatibility)
    locations: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run** `uv run pytest tests/domain/test_preferences.py -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/domain/preferences.py tests/domain/test_preferences.py
git commit -m "feat: expand Preferences into structured fields" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: required_years(description) helper

**Files:** Create `src/startup_agent/matching/experience.py`; Test `tests/matching/test_experience.py`.

- [ ] **Step 1: Write the failing test**

```python
from startup_agent.matching.experience import required_years


def test_extracts_minimum_years():
    assert required_years("We need 5+ years of experience in backend") == 5
    assert required_years("Minimum 7 years experience required") == 7
    assert required_years("3-5 years of experience") == 3       # lower bound of a range
    assert required_years("at least 8 years") == 8


def test_no_years_returns_none():
    assert required_years("Great backend role, join us!") is None
    assert required_years(None) is None
    assert required_years("") is None
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/matching/experience.py`:

```python
import re

# Matches "5+ years", "5 years", "minimum 5 years", "at least 5 years",
# "3-5 years" (captures the lower bound). Looks for a number near "year(s)".
_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:\+|or more)?\s*-?\s*\d{0,2}\s*years?", re.I),
    re.compile(r"(\d{1,2})\s*yrs?", re.I),
]


def required_years(description: str | None) -> int | None:
    if not description:
        return None
    candidates: list[int] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(description):
            try:
                value = int(match.group(1))
            except (ValueError, TypeError):
                continue
            if 0 < value <= 20:  # sane bound; ignore noise like "2024 years"
                candidates.append(value)
    return min(candidates) if candidates else None
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: add required_years description parser`.

---

### Task 3: Generalize location to district-driven

**Files:** Modify `src/startup_agent/matching/location.py`; Modify `tests/matching/test_location.py`.

- [ ] **Step 1: Update the test** — replace `test_location_allowed_rule` and the foreign-remote test to use the new signature `region_allowed(location, districts, include_remote)`:

```python
from startup_agent.matching.location import classify_location, region_allowed, Region


def test_region_allowed_respects_chosen_districts():
    # center selected, remote on
    assert region_allowed("Tel Aviv", {"center"}, True) is True
    assert region_allowed("Haifa", {"center"}, True) is False          # north not selected
    assert region_allowed("Haifa", {"center", "north"}, True) is True  # north selected
    assert region_allowed("Jerusalem", {"jerusalem"}, True) is True
    # remote handling
    assert region_allowed("Remote", {"center"}, True) is True
    assert region_allowed("Remote", {"center"}, False) is False        # remote off
    assert region_allowed("India - Remote", {"center"}, True) is False # foreign-pinned remote
    # empty districts = no location constraint (keep all non-foreign)
    assert region_allowed("Haifa", set(), True) is True
    # unknown w/ israel marker kept; missing dropped
    assert region_allowed("Kiryat Ono, Israel", {"center"}, True) is True
    assert region_allowed(None, {"center"}, True) is False
```

(Keep the existing `test_classifies_regions` — `classify_location` is unchanged.)

- [ ] **Step 2: Run** `uv run pytest tests/matching/test_location.py -v` → FAIL (`region_allowed` missing).
- [ ] **Step 3: Implement** — in `src/startup_agent/matching/location.py`, replace `location_allowed` with `region_allowed` (keep `classify_location`, `_CENTER`, `_REMOTE_FILLER`, `_is_location_agnostic_remote`):

```python
_REGION_NAME = {
    Region.CENTER: "center", Region.NORTH: "north",
    Region.SOUTH: "south", Region.JERUSALEM: "jerusalem",
}


def region_allowed(location: str | None, districts: set[str], include_remote: bool) -> bool:
    if not location:
        return False
    text = location.lower()
    region = classify_location(location)

    if region == Region.REMOTE:
        return include_remote and _is_location_agnostic_remote(text)

    if region in _REGION_NAME:
        name = _REGION_NAME[region]
        # empty districts = no constraint: keep any Israeli region
        return not districts or name in districts

    # UNKNOWN: keep only if it clearly names Israel / EMEA / a center city
    if "israel" in text or "emea" in text or any(city in text for city in _CENTER):
        return not districts or "center" in districts or "israel" in text
    return False
```

- [ ] **Step 4: Run** `uv run pytest tests/matching/test_location.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: district-driven region_allowed (replaces hardcoded center-only)`.

---

### Task 4: Generalize the hard prefilter

**Files:** Modify `src/startup_agent/matching/prefilter.py`; Modify `tests/matching/test_prefilter.py`.

- [ ] **Step 1: Replace the test file** `tests/matching/test_prefilter.py`:

```python
from datetime import datetime, timedelta, timezone

from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.prefilter import passes_prefilter

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _job(title, location="Tel Aviv", description="", posted_days_ago=1):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location=location, description=description,
               posted_at=NOW - timedelta(days=posted_days_ago))


def test_title_include_and_exclude():
    p = Preferences(title_include=["engineer"], exclude=["senior"])
    assert passes_prefilter(_job("Backend Engineer"), p, now=NOW) is True
    assert passes_prefilter(_job("Senior Backend Engineer"), p, now=NOW) is False
    assert passes_prefilter(_job("Product Manager"), p, now=NOW) is False  # no include kw


def test_district_filter():
    p = Preferences(districts=["center"], title_include=["engineer"])
    assert passes_prefilter(_job("Engineer", location="Haifa"), p, now=NOW) is False
    assert passes_prefilter(_job("Engineer", location="Tel Aviv"), p, now=NOW) is True


def test_max_years_filter():
    p = Preferences(max_years=3, title_include=["engineer"])
    assert passes_prefilter(_job("Engineer", description="requires 7+ years"), p, now=NOW) is False
    assert passes_prefilter(_job("Engineer", description="2 years experience"), p, now=NOW) is True
    assert passes_prefilter(_job("Engineer", description="no years mentioned"), p, now=NOW) is True  # unknown kept


def test_freshness_filter():
    p = Preferences(posted_within_days=7, title_include=["engineer"])
    assert passes_prefilter(_job("Engineer", posted_days_ago=2), p, now=NOW) is True
    assert passes_prefilter(_job("Engineer", posted_days_ago=30), p, now=NOW) is False


def test_empty_prefs_keep_everything_relevant():
    p = Preferences()  # no constraints
    assert passes_prefilter(_job("Anything", location="Haifa"), p, now=NOW) is True
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/matching/prefilter.py`:

```python
from datetime import datetime, timezone

from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.experience import required_years
from startup_agent.matching.location import region_allowed


def passes_prefilter(job: Job, preferences: Preferences,
                     now: datetime | None = None) -> bool:
    title = job.title.lower()

    # title exclude / include
    if any(term.lower() in title for term in preferences.exclude):
        return False
    if preferences.title_include and not any(
        term.lower() in title for term in preferences.title_include
    ):
        return False

    # district / remote
    if not region_allowed(job.location, set(preferences.districts), preferences.include_remote):
        return False

    # max experience years (drop only when the job states MORE than allowed)
    if preferences.max_years is not None:
        needed = required_years(job.description)
        if needed is not None and needed > preferences.max_years:
            return False

    # freshness
    if preferences.posted_within_days is not None and job.posted_at is not None:
        now = now or datetime.now(timezone.utc)
        age_days = (now - job.posted_at.astimezone(timezone.utc)).days
        if age_days > preferences.posted_within_days:
            return False

    return True
```

- [ ] **Step 4: Run** `uv run pytest tests/matching/test_prefilter.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: preference-driven hard prefilter (district/years/freshness/title)`.

---

### Task 5: Soft scoring + wire into matching

**Files:** Create `src/startup_agent/matching/soft_score.py`; Modify `src/startup_agent/services/matching.py`; Test `tests/matching/test_soft_score.py`.

- [ ] **Step 1: Write the failing test**

```python
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.soft_score import soft_adjust


def _job(title, description=""):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location="Tel Aviv", description=description)


def test_role_match_boosts_score():
    p = Preferences(roles=["backend"])
    boosted = soft_adjust(_job("Backend Engineer", "build backend services"), p, 0.50)
    none = soft_adjust(_job("Frontend Engineer", "build UIs"), p, 0.50)
    assert boosted > 0.50
    assert none == 0.50


def test_seniority_mismatch_penalizes():
    p = Preferences(seniority=["junior", "mid"])
    ok = soft_adjust(_job("Backend Engineer", "mid-level role"), p, 0.50)
    senior = soft_adjust(_job("Backend Engineer", "senior staff principal role"), p, 0.50)
    assert senior < ok


def test_no_soft_prefs_is_noop():
    assert soft_adjust(_job("Backend Engineer"), Preferences(), 0.50) == 0.50
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/matching/soft_score.py`:

```python
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

_ROLE_BONUS = 0.05
_SENIORITY_PENALTY = 0.05
_SENIOR_MARKERS = ("senior", "staff", "principal", "lead", "director")


def soft_adjust(job: Job, preferences: Preferences, base: float) -> float:
    text = f"{job.title} {job.description or ''}".lower()
    score = base

    if preferences.roles and any(role.lower() in text for role in preferences.roles):
        score += _ROLE_BONUS

    # if user wants junior/mid only and the job reads senior, nudge down
    wants_junior = any(s.lower() in ("junior", "mid", "entry", "associate")
                       for s in preferences.seniority)
    if wants_junior and any(marker in text for marker in _SENIOR_MARKERS):
        score -= _SENIORITY_PENALTY

    return score
```

- [ ] **Step 4: Wire into matching** — in `src/startup_agent/services/matching.py` `run()`, apply the soft adjustment to the cosine score:

Replace the scoring loop body:
```python
        from startup_agent.matching.soft_score import soft_adjust
        scored: list[tuple[Job, float]] = []
        for job in candidates:
            base = cosine(cv_vector, self._job_vector(job))
            score = soft_adjust(job, self._preferences, base)
            if score >= self._threshold:
                scored.append((job, score))
```

- [ ] **Step 5: Run** `uv run pytest tests/matching -v && uv run pytest tests/services/test_matching.py -v` → PASS.
- [ ] **Step 6: Commit** `feat: soft preference scoring (role boost, seniority penalty) in matching`.

---

### Task 6: Preferences storage in SQLite

**Files:** Modify `src/startup_agent/adapters/storage/schema.sql`, `src/startup_agent/adapters/storage/sqlite_repository.py`, `src/startup_agent/ports/repository.py`; Test `tests/adapters/storage/test_sqlite_repository.py` (append).

- [ ] **Step 1: Write the failing test**

```python
def test_save_and_get_preferences(repo):
    from startup_agent.domain.preferences import Preferences
    assert repo.get_preferences() is None
    repo.save_preferences(Preferences(districts=["center"], max_years=3, roles=["backend"]))
    loaded = repo.get_preferences()
    assert loaded.districts == ["center"]
    assert loaded.max_years == 3
    assert loaded.roles == ["backend"]


def test_save_preferences_replaces(repo):
    from startup_agent.domain.preferences import Preferences
    repo.save_preferences(Preferences(max_years=3))
    repo.save_preferences(Preferences(max_years=5))
    assert repo.get_preferences().max_years == 5
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Schema** — add to `schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS preferences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    json       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

- [ ] **Step 4: Port** — add to `JobRepository` ABC (`ports/repository.py`):

```python
    @abstractmethod
    def save_preferences(self, preferences: "Preferences") -> None: ...

    @abstractmethod
    def get_preferences(self) -> "Preferences | None": ...
```

(Add `from startup_agent.domain.preferences import Preferences` at top.)

- [ ] **Step 5: Implement** in `SQLiteJobRepository`:

```python
    def save_preferences(self, preferences) -> None:
        self._conn.execute("DELETE FROM preferences")
        self._conn.execute(
            "INSERT INTO preferences (json, updated_at) VALUES (?, ?)",
            (preferences.model_dump_json(), _now()),
        )
        self._conn.commit()

    def get_preferences(self):
        from startup_agent.domain.preferences import Preferences
        row = self._conn.execute(
            "SELECT json FROM preferences ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Preferences.model_validate_json(row["json"])
```

- [ ] **Step 6: Run** `uv run pytest tests/adapters/storage -v` → PASS. Full suite `uv run pytest -q` → green.
- [ ] **Step 7: Commit** `feat: persist preferences in SQLite (save/get)`.

---

### Task 7: Preferences API + wire run/results to stored prefs

**Files:** Create `api/routes/preferences.py`; Modify `api/main.py`, `api/matching_view.py`, `api/routes/run.py`; Test `tests/api/test_preferences.py`.

- [ ] **Step 1: Write the failing test** (`tests/api/test_preferences.py`)

```python
def test_get_preferences_returns_defaults_when_unset(client):
    resp = client.get("/api/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["districts"] == []
    assert body["include_remote"] is True


def test_put_then_get_preferences_round_trip(client):
    payload = {"districts": ["center", "north"], "include_remote": False,
               "max_years": 3, "posted_within_days": 30,
               "roles": ["backend"], "seniority": ["junior"],
               "title_include": ["engineer"], "exclude": ["senior"]}
    put = client.put("/api/preferences", json=payload)
    assert put.status_code == 200
    got = client.get("/api/preferences").json()
    assert got["districts"] == ["center", "north"]
    assert got["max_years"] == 3
```

- [ ] **Step 2: Run** → FAIL (404).
- [ ] **Step 3: Implement** `api/routes/preferences.py`:

```python
from fastapi import APIRouter, Depends

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.preferences import Preferences

from api.deps import get_settings

router = APIRouter()


@router.get("/preferences")
def get_preferences(settings=Depends(get_settings)) -> Preferences:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    return repo.get_preferences() or Preferences()


@router.put("/preferences")
def put_preferences(prefs: Preferences, settings=Depends(get_settings)) -> dict:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.save_preferences(prefs)
    return {"status": "saved"}
```

Mount in `api/main.py` (`from api.routes import ..., preferences` and `app.include_router(preferences.router, prefix="/api")`).

- [ ] **Step 4: Make matching use stored prefs** — add a helper in `api/matching_view.py` and use it in `compute_matches` + run route. Change `compute_matches` to load prefs from the repo instead of the yaml path:

```python
def _load_prefs(repo, preferences_path):
    stored = repo.get_preferences()
    if stored is not None:
        return stored
    from startup_agent.config.preferences_loader import load_preferences
    return load_preferences(preferences_path)
```

In `compute_matches`, replace `prefs = load_preferences(preferences_path)` with `prefs = _load_prefs(repo, preferences_path)`. (The `run.py` route already calls `compute_matches`; it now honors stored prefs automatically.)

- [ ] **Step 5: Run** `uv run pytest tests/api -v && uv run pytest -q` → PASS/green. `uv run ruff check src api tests`.
- [ ] **Step 6: Commit** `feat: preferences API (GET/PUT) + matching uses stored prefs`.

---

### Task 8: Frontend — Preferences screen in the flow

**Files:** Modify `frontend/src/api/client.ts`; Create `frontend/src/components/PreferencesForm.tsx`; Modify `frontend/src/App.tsx`; Modify `frontend/src/styles/app.css`.

- [ ] **Step 1: Add to `frontend/src/api/client.ts`**

```ts
export interface Preferences {
  districts: string[];
  include_remote: boolean;
  max_years: number | null;
  posted_within_days: number | null;
  title_include: string[];
  exclude: string[];
  roles: string[];
  seniority: string[];
  locations: string[];
  must_have: string[];
}

export async function getPreferences(): Promise<Preferences> {
  const resp = await fetch("/api/preferences");
  if (!resp.ok) throw new Error(`Load prefs failed (${resp.status})`);
  return resp.json();
}

export async function savePreferences(prefs: Preferences): Promise<void> {
  const resp = await fetch("/api/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!resp.ok) throw new Error(`Save prefs failed (${resp.status})`);
}
```

- [ ] **Step 2: Create `frontend/src/components/PreferencesForm.tsx`** — chips for multi-selects, number inputs, toggle:

```tsx
import { useEffect, useState } from "react";
import { getPreferences, savePreferences, type Preferences } from "../api/client";

const DISTRICTS = ["center", "north", "south", "jerusalem"];
const ROLES = ["backend", "frontend", "full-stack", "ai", "data", "devops", "security"];
const SENIORITY = ["junior", "mid", "senior"];

function Chips({ options, selected, onToggle }:
  { options: string[]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="chips">
      {options.map((o) => (
        <button key={o} type="button"
          className={`chip ${selected.includes(o) ? "chip-on" : ""}`}
          onClick={() => onToggle(o)}>{o}</button>
      ))}
    </div>
  );
}

export function PreferencesForm({ onSaved }: { onSaved: () => void }) {
  const [p, setP] = useState<Preferences | null>(null);

  useEffect(() => { getPreferences().then(setP); }, []);
  if (!p) return <p className="muted">Loading preferences…</p>;

  const toggle = (key: "districts" | "roles" | "seniority", v: string) =>
    setP({ ...p, [key]: p[key].includes(v) ? p[key].filter((x) => x !== v) : [...p[key], v] });

  async function save() { await savePreferences(p!); onSaved(); }

  return (
    <div className="card prefs">
      <h3>Your preferences</h3>

      <label className="prefs-label">Districts <span className="hard">· hard</span></label>
      <Chips options={DISTRICTS} selected={p.districts} onToggle={(v) => toggle("districts", v)} />
      <label className="prefs-check">
        <input type="checkbox" checked={p.include_remote}
          onChange={(e) => setP({ ...p, include_remote: e.target.checked })} /> Include remote
      </label>

      <label className="prefs-label">Max experience (years) <span className="hard">· hard</span></label>
      <input className="prefs-num" type="number" min={0} max={20}
        value={p.max_years ?? ""} placeholder="no limit"
        onChange={(e) => setP({ ...p, max_years: e.target.value ? Number(e.target.value) : null })} />

      <label className="prefs-label">Posted within (days) <span className="hard">· hard</span></label>
      <input className="prefs-num" type="number" min={1} max={365}
        value={p.posted_within_days ?? ""} placeholder="any time"
        onChange={(e) => setP({ ...p, posted_within_days: e.target.value ? Number(e.target.value) : null })} />

      <label className="prefs-label">Role / domain <span className="soft">★ soft</span></label>
      <Chips options={ROLES} selected={p.roles} onToggle={(v) => toggle("roles", v)} />

      <label className="prefs-label">Seniority <span className="soft">★ soft</span></label>
      <Chips options={SENIORITY} selected={p.seniority} onToggle={(v) => toggle("seniority", v)} />

      <button className="primary" onClick={save}>Save & Find jobs →</button>
    </div>
  );
}
```

- [ ] **Step 3: Insert the phase in `frontend/src/App.tsx`** — add `"preferences"` between upload and running. After CV upload, go to preferences (not straight to run); saving prefs starts the run:

```tsx
type Phase = "upload" | "preferences" | "running" | "results";
// ...
{phase === "upload" && <CvUpload onReady={() => setPhase("preferences")} />}
{phase === "preferences" && <PreferencesForm onSaved={start} />}
{phase === "running" && <RunProgress last={last} />}
{phase === "results" && (/* existing results block */)}
```

(Import `PreferencesForm`. `start()` already kicks off `runStream` and moves to "running".)

- [ ] **Step 4: Add styles** to `frontend/src/styles/app.css`:

```css
.prefs { max-width: 560px; text-align: left; }
.prefs-label { display: block; font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; margin: 16px 0 6px; }
.hard { color: #b91c1c; } .soft { color: var(--accent); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: var(--accent-soft); color: var(--accent); border: 1px solid transparent; border-radius: 20px; padding: 5px 12px; font-size: 13px; cursor: pointer; }
.chip-on { background: var(--accent); color: #fff; }
.prefs-check { display: block; margin-top: 8px; font-size: 14px; }
.prefs-num { width: 120px; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 8px; }
.primary { margin-top: 20px; width: 100%; background: var(--accent); color: #fff; border: none; border-radius: 10px; padding: 11px; font-weight: 700; cursor: pointer; }
```

- [ ] **Step 5: Build** `cd frontend && npm run build` → clean.
- [ ] **Step 6: Commit** `feat(web): preferences screen in the flow (upload -> preferences -> run)`.

---

### Task 9: Live smoke + checkpoint

- [ ] **Step 1:** Full backend suite + lint: `uv run pytest -q && uv run ruff check src api tests` → green.
- [ ] **Step 2:** Live: `make dev`, open `http://localhost:5173`, upload CV → set preferences (e.g. Center only, max 3 years, roles backend+ai) → Save & Find jobs → confirm results respect the prefs (no Haifa, no 7-year roles, backend/AI ranked up). Re-run with different prefs and confirm the list changes.
- [ ] **Step 3:** Merge `phase-7/user-preferences` → `main`.

> **Checkpoint:** preferences are user-editable and drive matching, no key needed. Phase 2 (LLM auto-fill from CV) gets its own plan.

---

## Self-Review Notes

- **Spec coverage:** structured fields §3 → Task 1 (the 7 feasible; employment/company-type explicitly deferred per the scope note, matching the "no backing data" reality); max-years §3/§5 → Tasks 2,4; districts/remote → Task 3; hard prefilter §5.1 → Task 4; soft scoring §5.2 → Task 5; SQLite storage §6 → Task 6; API §6 + run uses stored prefs → Task 7; Preferences UI screen + flow §6/§12 → Task 8; testing §9 → tests in every task; build order §10 Phase 1 → this whole plan; Phase 2 (LLM autofill, §4/§10) → deferred to its own plan.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `Preferences` field names (districts, include_remote, max_years, posted_within_days, title_include, exclude, roles, seniority) identical across model, prefilter, soft_score, repo, API, and the TS `Preferences` interface. `region_allowed(location, districts:set, include_remote)`, `required_years(description)`, `soft_adjust(job, prefs, base)`, `passes_prefilter(job, prefs, now=None)`, repo `save_preferences/get_preferences` — consistent across tasks.
- **Deferred-with-data-note:** employment-type and company-type are intentionally NOT built in Phase 1 (no persisted `employment_type` on Job, no startup/enterprise tag on Company). A follow-up must add that data plumbing first; building the filters now would be dead code.
