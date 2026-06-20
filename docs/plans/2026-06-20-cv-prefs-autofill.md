# CV → Preferences Auto-fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** An "✨ Auto-fill from CV" button on the Preferences screen that uses the LLM to suggest the CV-inferable preference fields (max_years, roles, seniority, title_include), pre-fills the form, and lets the user review/edit before saving.

**Architecture:** A `CvPreferenceSuggester` port with Claude + OpenAI adapters (mirrors the ranker), chosen by the same provider/key config as `get_ranker`; a `POST /api/preferences/suggest` route that merges the inferable fields onto current prefs; a button in `PreferencesForm` that merges only those fields into the form. Reuses the existing LLM key config (UI-memory or `.env`).

**Tech Stack:** Python 3.13, pydantic v2, anthropic + openai SDKs, FastAPI, React+Vite+TS. All backend tests offline with mocked suggesters.

**Repo discipline:** Work ONLY in `/Users/netanelsade/projects/startup-agent`; never touch `/Users/netanelsade/conifers`. Branch `phase-11/cv-prefs-autofill`. Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File structure
```
src/startup_agent/ports/cv_suggester.py              NEW: CvPreferenceSuggester
src/startup_agent/adapters/suggesting/__init__.py    NEW (empty)
src/startup_agent/adapters/suggesting/prompt.py       NEW: vocab + instructions + to_preferences()
src/startup_agent/adapters/suggesting/claude_suggester.py  NEW: ClaudeCvSuggester
src/startup_agent/adapters/suggesting/openai_suggester.py  NEW: OpenAICvSuggester
api/deps.py                                          MODIFY: build_suggester_from + get_suggester
api/routes/preferences.py                            MODIFY: POST /api/preferences/suggest
frontend/src/api/client.ts                           suggestPreferences()
frontend/src/components/PreferencesForm.tsx          "✨ Auto-fill from CV" button
frontend/src/styles/app.css                          button style
```

---

### Task 1: Suggester port + shared prompt/validation + ClaudeCvSuggester

**Files:** Create `src/startup_agent/ports/cv_suggester.py`, `src/startup_agent/adapters/suggesting/__init__.py`, `src/startup_agent/adapters/suggesting/prompt.py`, `src/startup_agent/adapters/suggesting/claude_suggester.py`; Test `tests/adapters/suggesting/__init__.py` (empty), `tests/adapters/suggesting/test_prompt.py`, `tests/adapters/suggesting/test_claude_suggester.py`.

- [ ] **Step 1: Write the failing tests**

`tests/adapters/suggesting/test_prompt.py`:
```python
from startup_agent.adapters.suggesting.prompt import to_preferences


def test_to_preferences_keeps_only_inferable_and_drops_out_of_vocab():
    p = to_preferences({"max_years": 3, "roles": ["backend", "ai", "blockchain"],
                        "seniority": ["junior", "wizard"], "title_include": ["engineer"]})
    assert p.max_years == 3
    assert p.roles == ["backend", "ai"]          # "blockchain" dropped (out of vocab)
    assert p.seniority == ["junior"]             # "wizard" dropped
    assert p.title_include == ["engineer"]
    # pure-preference fields stay at defaults (suggester never sets them)
    assert p.districts == [] and p.include_remote is True and p.posted_within_days is None


def test_to_preferences_tolerates_missing_fields():
    p = to_preferences({})
    assert p.max_years is None and p.roles == [] and p.seniority == []
```

`tests/adapters/suggesting/test_claude_suggester.py`:
```python
from types import SimpleNamespace

from startup_agent.adapters.suggesting.claude_suggester import ClaudeCvSuggester


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=SimpleNamespace(
            max_years=3, roles=["backend", "ai"], seniority=["junior", "mid"],
            title_include=["engineer"]))


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_claude_suggester_returns_preferences_from_cv():
    client = _FakeClient()
    prefs = ClaudeCvSuggester(client=client, model="claude-opus-4-8").suggest("MY CV TEXT")
    assert prefs.max_years == 3
    assert prefs.roles == ["backend", "ai"]
    assert prefs.seniority == ["junior", "mid"]
    assert prefs.title_include == ["engineer"]
    # CV text reached the prompt
    blob = str(client.messages.calls[0])
    assert "MY CV TEXT" in blob
```

- [ ] **Step 2: Run** `uv run pytest tests/adapters/suggesting -v` → FAIL (modules missing).
- [ ] **Step 3: Implement** `src/startup_agent/ports/cv_suggester.py`:

```python
from abc import ABC, abstractmethod

from startup_agent.domain.preferences import Preferences


class CvPreferenceSuggester(ABC):
    @abstractmethod
    def suggest(self, cv_text: str) -> Preferences: ...
```

`src/startup_agent/adapters/suggesting/prompt.py`:

```python
from startup_agent.domain.preferences import Preferences

ROLE_VOCAB = ["backend", "frontend", "full-stack", "ai", "data", "devops", "security"]
SENIORITY_VOCAB = ["junior", "mid", "senior"]

INSTRUCTIONS = (
    "You read a candidate's CV and infer ONLY what the CV actually reveals: "
    "a sensible maximum years-of-experience to target (an integer), the role/domain(s), "
    "the seniority level, and relevant job-title keywords. "
    f"roles MUST be chosen from: {ROLE_VOCAB}. "
    f"seniority MUST be chosen from: {SENIORITY_VOCAB}. "
    "Do NOT infer location, district, or remote preferences. "
    'Return JSON: {"max_years": <int>, "roles": [...], "seniority": [...], "title_include": [...]}.'
)


def to_preferences(data: dict) -> Preferences:
    """Validate a raw suggestion dict into a Preferences (inferable fields only)."""
    roles = [r for r in (data.get("roles") or []) if r in ROLE_VOCAB]
    seniority = [s for s in (data.get("seniority") or []) if s in SENIORITY_VOCAB]
    title_include = [str(t) for t in (data.get("title_include") or [])]
    max_years = data.get("max_years")
    if max_years is not None:
        try:
            max_years = int(max_years)
        except (ValueError, TypeError):
            max_years = None
    return Preferences(max_years=max_years, roles=roles, seniority=seniority,
                       title_include=title_include)
```

`src/startup_agent/adapters/suggesting/claude_suggester.py`:

```python
import anthropic
from pydantic import BaseModel

from startup_agent.adapters.suggesting.prompt import INSTRUCTIONS, to_preferences
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.cv_suggester import CvPreferenceSuggester


class _Suggestion(BaseModel):
    max_years: int | None = None
    roles: list[str] = []
    seniority: list[str] = []
    title_include: list[str] = []


class ClaudeCvSuggester(CvPreferenceSuggester):
    def __init__(self, api_key: str = "", model: str = "claude-opus-4-8",
                 client: object | None = None) -> None:
        self._client = client or (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self._model = model

    def suggest(self, cv_text: str) -> Preferences:
        message = self._client.messages.parse(
            model=self._model,
            max_tokens=600,
            system=[{"type": "text", "text": INSTRUCTIONS}],
            messages=[{"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nInfer the preferences."}],
            output_format=_Suggestion,
        )
        s = message.parsed_output
        return to_preferences({"max_years": s.max_years, "roles": s.roles,
                               "seniority": s.seniority, "title_include": s.title_include})
```

Create empty `src/startup_agent/adapters/suggesting/__init__.py` and `tests/adapters/suggesting/__init__.py`.

- [ ] **Step 4: Run** `uv run pytest tests/adapters/suggesting -v` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/ports/cv_suggester.py src/startup_agent/adapters/suggesting tests/adapters/suggesting
git commit -m "feat: CvPreferenceSuggester port + shared prompt + ClaudeCvSuggester" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: OpenAICvSuggester

**Files:** Create `src/startup_agent/adapters/suggesting/openai_suggester.py`; Test `tests/adapters/suggesting/test_openai_suggester.py`.

- [ ] **Step 1: Write the failing test**

```python
import json
from types import SimpleNamespace

from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"max_years": 3, "roles": ["backend"], "seniority": ["mid"],
                              "title_include": ["engineer"]})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_openai_suggester_returns_preferences():
    client = _FakeClient()
    prefs = OpenAICvSuggester(client=client, model="gpt-4o").suggest("MY CV")
    assert prefs.max_years == 3
    assert prefs.roles == ["backend"]
    assert prefs.seniority == ["mid"]
    assert "MY CV" in str(client.chat.completions.calls[0])
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/adapters/suggesting/openai_suggester.py`:

```python
import json

from startup_agent.adapters.suggesting.prompt import INSTRUCTIONS, to_preferences
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.cv_suggester import CvPreferenceSuggester


class OpenAICvSuggester(CvPreferenceSuggester):
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

    def suggest(self, cv_text: str) -> Preferences:
        completion = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nInfer the preferences."},
            ],
        )
        data = json.loads(completion.choices[0].message.content)
        return to_preferences(data)
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: add OpenAICvSuggester`.

---

### Task 3: build_suggester_from + get_suggester

**Files:** Modify `api/deps.py`; Test `tests/api/test_get_suggester.py`.

- [ ] **Step 1: Write the failing test**

```python
from startup_agent.config.settings import Settings
from api import deps, llm_config


def test_build_suggester_none_without_key():
    assert deps.build_suggester_from("anthropic", "") is None


def test_build_suggester_anthropic_and_openai():
    from startup_agent.adapters.suggesting.claude_suggester import ClaudeCvSuggester
    from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester
    assert isinstance(deps.build_suggester_from("anthropic", "sk-x", "claude-opus-4-8"), ClaudeCvSuggester)
    assert isinstance(deps.build_suggester_from("openai", "sk-x", "gpt-4o"), OpenAICvSuggester)


def test_get_suggester_prefers_in_memory_config():
    from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester
    llm_config.clear_config()
    llm_config.set_config("openai", "sk-mem", "gpt-4o")
    try:
        assert isinstance(deps.get_suggester(), OpenAICvSuggester)
    finally:
        llm_config.clear_config()
```

- [ ] **Step 2: Run** `uv run pytest tests/api/test_get_suggester.py -v` → FAIL.
- [ ] **Step 3: Implement** — add to `api/deps.py`:

```python
def build_suggester_from(provider: str, api_key: str, model: str = "", base_url: str = ""):
    """Build a CvPreferenceSuggester from raw config, or None when no key is given."""
    if not api_key:
        return None
    if (provider or "anthropic").lower() == "openai":
        from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester
        return OpenAICvSuggester(api_key=api_key, model=model or "gpt-4o", base_url=base_url)
    from startup_agent.adapters.suggesting.claude_suggester import ClaudeCvSuggester
    return ClaudeCvSuggester(api_key=api_key, model=model or "claude-opus-4-8")


def get_suggester():
    from api.llm_config import get_config
    cfg = get_config()
    if cfg is not None:
        return build_suggester_from(cfg["provider"], cfg["api_key"], cfg.get("model", ""))
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        return build_suggester_from("openai", settings.openai_api_key,
                                    settings.openai_model, settings.openai_base_url)
    return build_suggester_from("anthropic", settings.anthropic_api_key, settings.llm_model)
```

- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: build_suggester_from + get_suggester (mirrors ranker)`.

---

### Task 4: POST /api/preferences/suggest

**Files:** Modify `api/routes/preferences.py`; Test `tests/api/test_preferences_suggest.py`.

- [ ] **Step 1: Write the failing test**

```python
import io
from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.preferences import Preferences


def _pdf():
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    b = io.BytesIO(); w.write(b); return b.getvalue()


class _FakeSuggester:
    def suggest(self, cv_text):
        return Preferences(max_years=3, roles=["backend"], seniority=["junior"],
                           title_include=["engineer"])


def test_suggest_merges_inferable_onto_current(client, settings):
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    # current prefs have user-chosen districts/remote we must NOT overwrite
    repo.save_preferences(Preferences(districts=["center"], include_remote=False,
                                      posted_within_days=14))
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_suggester] = lambda: _FakeSuggester()

    resp = client.post("/api/preferences/suggest")
    assert resp.status_code == 200
    body = resp.json()
    # inferable fields came from the suggester
    assert body["max_years"] == 3 and body["roles"] == ["backend"]
    assert body["seniority"] == ["junior"] and body["title_include"] == ["engineer"]
    # pure-preference fields preserved from current
    assert body["districts"] == ["center"] and body["include_remote"] is False
    assert body["posted_within_days"] == 14


def test_suggest_without_llm_returns_400(client, settings):
    app.dependency_overrides[deps.get_suggester] = lambda: None
    resp = client.post("/api/preferences/suggest")
    assert resp.status_code == 400


def test_suggest_without_cv_returns_400(client, settings):
    app.dependency_overrides[deps.get_suggester] = lambda: _FakeSuggester()
    resp = client.post("/api/preferences/suggest")  # no CV uploaded
    assert resp.status_code == 400
```

- [ ] **Step 2: Run** `uv run pytest tests/api/test_preferences_suggest.py -v` → FAIL (404).
- [ ] **Step 3: Implement** — add to `api/routes/preferences.py` (extend imports: `Depends`, `HTTPException`, `get_suggester`):

```python
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_settings, get_suggester
# ... existing routes ...


@router.post("/preferences/suggest")
def suggest_preferences(suggester=Depends(get_suggester),
                        settings=Depends(get_settings)) -> Preferences:
    if suggester is None:
        raise HTTPException(status_code=400, detail="No LLM configured. Add a key in AI scoring.")
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    current = repo.get_preferences() or Preferences()
    suggestion = suggester.suggest(cv["text"])
    return current.model_copy(update={
        "max_years": suggestion.max_years,
        "roles": suggestion.roles,
        "seniority": suggestion.seniority,
        "title_include": suggestion.title_include,
    })
```

- [ ] **Step 4: Run** `uv run pytest tests/api -v && uv run pytest -q` → green. `uv run ruff check src api tests`.
- [ ] **Step 5: Commit** `feat: POST /api/preferences/suggest (merge inferable onto current)`.

---

### Task 5: Frontend — "✨ Auto-fill from CV" button

**Files:** Modify `frontend/src/api/client.ts`, `frontend/src/components/PreferencesForm.tsx`, `frontend/src/styles/app.css`.

- [ ] **Step 1: client.ts** — add (keep existing exports):

```ts
export async function suggestPreferences(): Promise<Preferences> {
  const resp = await fetch("/api/preferences/suggest", { method: "POST" });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail || `Auto-fill failed (${resp.status})`);
  }
  return resp.json();
}
```

- [ ] **Step 2: PreferencesForm.tsx** — add an auto-fill button that merges ONLY the inferable fields, plus a disabled state when no LLM is configured. Read the current file first; integrate without removing fields. Add the imports and state:

```tsx
import { getLlmConfig, suggestPreferences } from "../api/client";
```

Inside the component (alongside the existing `p` state):

```tsx
  const [aiOn, setAiOn] = useState(false);
  const [autofilling, setAutofilling] = useState(false);
  const [autofillErr, setAutofillErr] = useState<string | null>(null);

  useEffect(() => { getLlmConfig().then((c) => setAiOn(c.configured)); }, []);

  async function autofill() {
    setAutofilling(true); setAutofillErr(null);
    try {
      const s = await suggestPreferences();
      setP((cur) => cur && ({
        ...cur,
        max_years: s.max_years, roles: s.roles,
        seniority: s.seniority, title_include: s.title_include,
      }));
    } catch (e) { setAutofillErr(e instanceof Error ? e.message : "Auto-fill failed"); }
    finally { setAutofilling(false); }
  }
```

Render the button just under the `<h3>Your preferences</h3>` line:

```tsx
      <button className="autofill-btn" onClick={autofill}
              disabled={!aiOn || autofilling}
              title={aiOn ? "" : "Add a key in AI scoring below to enable"}>
        {autofilling ? "Reading your CV…" : "✨ Auto-fill from CV"}
      </button>
      {!aiOn && <p className="muted autofill-hint">Enable AI scoring below to auto-fill from your CV.</p>}
      {autofillErr && <p className="error">{autofillErr}</p>}
```

(`p[key]` toggle and the rest of the form stay as they are. The `setP((cur) => ...)` form is safe because `p` is non-null past the loading guard.)

- [ ] **Step 3: app.css** — add:

```css
.autofill-btn { margin: 4px 0 10px; background: #fff; color: var(--accent); border: 1px solid #c7d2fe; border-radius: 8px; padding: 7px 14px; font-size: 13px; font-weight: 600; cursor: pointer; }
.autofill-btn:disabled { opacity: .55; cursor: default; }
.autofill-hint { margin: 0 0 8px; }
```

- [ ] **Step 4: Build** `cd frontend && npm run build` → clean.
- [ ] **Step 5: Commit** `feat(web): Auto-fill from CV button (merges inferable prefs)`.

---

### Task 6: Live smoke + checkpoint

- [ ] **Step 1:** Backend suite + lint: `uv run pytest -q && uv run ruff check src api tests` → green.
- [ ] **Step 2:** `make dev`; on the Preferences screen with **no key**, the "✨ Auto-fill from CV" button is disabled with the hint. With a key configured (AI-scoring panel), clicking it fills max-years/roles/seniority/title from the CV and leaves districts/remote/freshness as set. *(Mocked-suggester tests already prove the wiring; a real fill needs a key.)*
- [ ] **Step 3:** Merge `phase-11/cv-prefs-autofill` → `main`.

> **Checkpoint:** CV→prefs auto-fill complete — provider-pluggable, merge-not-overwrite, review-before-save, reusing the LLM key config.

---

## Self-Review Notes

- **Spec coverage:** CV-inferable fields only §2 → `to_preferences` vocab-clamp (Task 1) + route merges only those 4 (Task 4); suggester port + Claude/OpenAI adapters §3 → Tasks 1,2; `get_suggester` mirrors ranker config §3 → Task 3; `POST /api/preferences/suggest` merging onto current §3/§4 → Task 4; button merges only inferable + disabled when unconfigured §3 → Task 5; error handling no-key/no-CV 400 + out-of-vocab dropped §5 → Tasks 1,4 tests; offline testing §6 → mocked suggesters throughout; scope (no district/remote suggestions, reuse key config) §7 → respected.
- **Placeholder scan:** none — concrete code/commands throughout.
- **Type consistency:** `CvPreferenceSuggester.suggest(cv_text) -> Preferences` consistent across port, both adapters, fakes, deps, route. `to_preferences(data: dict) -> Preferences`, `build_suggester_from(provider, api_key, model="", base_url="")`, `get_suggester()`, `suggestPreferences() -> Preferences`, `/api/preferences/suggest` path, and the four inferable field names (max_years/roles/seniority/title_include) all consistent. `current.model_copy(update={...})` matches the existing `job_match_from_result` pattern already used in the repo.
