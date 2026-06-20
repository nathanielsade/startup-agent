# Applicant Profile + Apply Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A saved applicant profile (standard form fields) extracted from the CV via regex (no key) + optional LLM (name/location/title), reusable on every job with copy buttons, a LinkedIn company-search link, and the existing open-application link. No cover letters, no auto-submit.

**Architecture:** `ApplicantProfile` domain model; a pure `regex_extract`; a `CvProfileExtractor` port with Claude/OpenAI adapters (mirrors the suggester); a `build_profile` service that merges regex + optional LLM (LLM failure → regex-only, never 500); SQLite `profile` table; `GET/PUT/POST /api/profile(/extract)`; a `ProfileForm` section + a per-job Apply panel.

**Tech Stack:** Python 3.13, pydantic v2, anthropic + openai SDKs, FastAPI, React+Vite+TS. All backend tests offline with mocked extractors.

**Repo discipline:** Work ONLY in `/Users/netanelsade/projects/startup-agent`; never touch `/Users/netanelsade/conifers`. Branch `phase-12/applicant-profile` (already created, spec committed there). Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. **Do NOT merge to `main` — the user reviews the running app first.**

## File structure
```
src/startup_agent/domain/applicant_profile.py            NEW: ApplicantProfile
src/startup_agent/profile/__init__.py                    NEW (empty)
src/startup_agent/profile/regex_extract.py               NEW: regex_extract()
src/startup_agent/ports/cv_profile_extractor.py          NEW: CvProfileExtractor
src/startup_agent/adapters/profiling/__init__.py         NEW (empty)
src/startup_agent/adapters/profiling/prompt.py            NEW: INSTRUCTIONS + to_profile()
src/startup_agent/adapters/profiling/claude_extractor.py  NEW: ClaudeProfileExtractor
src/startup_agent/adapters/profiling/openai_extractor.py  NEW: OpenAIProfileExtractor
src/startup_agent/services/profile_builder.py            NEW: build_profile()
src/startup_agent/adapters/storage/schema.sql            MODIFY: profile table
src/startup_agent/adapters/storage/sqlite_repository.py  MODIFY: save_profile/get_profile
api/deps.py                                              MODIFY: build_profile_extractor_from + get_profile_extractor
api/routes/profile.py                                    NEW: GET/PUT/POST routes
api/main.py                                              MODIFY: include profile.router
frontend/src/api/client.ts                               MODIFY: ApplicantProfile + 3 fns
frontend/src/components/ProfileForm.tsx                   NEW
frontend/src/App.tsx                                     MODIFY: render ProfileForm
frontend/src/components/JobList.tsx                       MODIFY: fetch + pass profile
frontend/src/components/JobCard.tsx                       MODIFY: Apply panel
frontend/src/styles/app.css                              MODIFY: styles
```

---

### Task 1: ApplicantProfile domain model + regex extractor

**Files:** Create `src/startup_agent/domain/applicant_profile.py`, `src/startup_agent/profile/__init__.py`, `src/startup_agent/profile/regex_extract.py`; Test `tests/profile/__init__.py` (empty), `tests/profile/test_regex_extract.py`.

- [ ] **Step 1: Write the failing test** `tests/profile/test_regex_extract.py`:

```python
from startup_agent.profile.regex_extract import regex_extract

CV = """
Netanel Sade
Backend Engineer
Email: netanelsbt@gmail.com  |  Phone: +972 54-123-4567
linkedin.com/in/netanel-sade   github.com/netanelSade1
Tel Aviv, Israel
"""


def test_regex_extract_pulls_contact_fields():
    d = regex_extract(CV)
    assert d["email"] == "netanelsbt@gmail.com"
    assert d["phone"].replace(" ", "") == "+97254-123-4567"
    assert d["linkedin_url"] == "https://linkedin.com/in/netanel-sade"
    assert d["github_url"] == "https://github.com/netanelSade1"


def test_regex_extract_absent_fields_omitted():
    d = regex_extract("just some text with no contacts")
    assert "email" not in d and "phone" not in d
    assert "linkedin_url" not in d and "github_url" not in d
```

- [ ] **Step 2: Run** `uv run pytest tests/profile -v` → FAIL (modules missing).

- [ ] **Step 3: Implement** `src/startup_agent/domain/applicant_profile.py`:

```python
from pydantic import BaseModel


class ApplicantProfile(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    location: str = ""
    current_title: str = ""
```

`src/startup_agent/profile/regex_extract.py`:

```python
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?(linkedin\.com/in/[\w\-%./]+)", re.I)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?(github\.com/[\w\-]+)", re.I)


def regex_extract(cv_text: str) -> dict:
    """Pull pattern-shaped contact fields from CV text. Missing fields are omitted."""
    out: dict = {}
    if m := _EMAIL.search(cv_text):
        out["email"] = m.group(0)
    if m := _PHONE.search(cv_text):
        out["phone"] = re.sub(r"\s+", " ", m.group(0)).strip()
    if m := _LINKEDIN.search(cv_text):
        out["linkedin_url"] = "https://" + m.group(1).rstrip("/.")
    if m := _GITHUB.search(cv_text):
        out["github_url"] = "https://" + m.group(1).rstrip("/.")
    return out
```

Create empty `src/startup_agent/profile/__init__.py` and `tests/profile/__init__.py`.

- [ ] **Step 4: Run** `uv run pytest tests/profile -v` → PASS. Run `uv run ruff check src tests`.
- [ ] **Step 5: Commit**

```bash
cd /Users/netanelsade/projects/startup-agent
git add src/startup_agent/domain/applicant_profile.py src/startup_agent/profile tests/profile
git commit -m "feat: ApplicantProfile model + regex contact extractor" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: CvProfileExtractor port + prompt/validation + ClaudeProfileExtractor

**Files:** Create `src/startup_agent/ports/cv_profile_extractor.py`, `src/startup_agent/adapters/profiling/__init__.py`, `src/startup_agent/adapters/profiling/prompt.py`, `src/startup_agent/adapters/profiling/claude_extractor.py`; Test `tests/adapters/profiling/__init__.py` (empty), `tests/adapters/profiling/test_prompt.py`, `tests/adapters/profiling/test_claude_extractor.py`.

- [ ] **Step 1: Write the failing tests** `tests/adapters/profiling/test_prompt.py`:

```python
from startup_agent.adapters.profiling.prompt import to_profile


def test_to_profile_keeps_only_judgment_fields():
    p = to_profile({"first_name": "Netanel", "last_name": "Sade",
                    "location": "Tel Aviv", "current_title": "Backend Engineer",
                    "email": "x@y.com"})  # email ignored — regex owns contact fields
    assert p.first_name == "Netanel" and p.last_name == "Sade"
    assert p.location == "Tel Aviv" and p.current_title == "Backend Engineer"
    assert p.email == "" and p.phone == ""


def test_to_profile_tolerates_missing_and_coerces_str():
    p = to_profile({"first_name": 5})
    assert p.first_name == "5" and p.last_name == "" and p.location == ""
```

`tests/adapters/profiling/test_claude_extractor.py`:

```python
from types import SimpleNamespace

from startup_agent.adapters.profiling.claude_extractor import ClaudeProfileExtractor


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=SimpleNamespace(
            first_name="Netanel", last_name="Sade",
            location="Tel Aviv", current_title="Backend Engineer"))


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_claude_extractor_returns_profile_from_cv():
    client = _FakeClient()
    p = ClaudeProfileExtractor(client=client, model="claude-opus-4-8").extract("MY CV TEXT")
    assert p.first_name == "Netanel" and p.last_name == "Sade"
    assert p.location == "Tel Aviv" and p.current_title == "Backend Engineer"
    assert "MY CV TEXT" in str(client.messages.calls[0])
```

- [ ] **Step 2: Run** `uv run pytest tests/adapters/profiling -v` → FAIL.

- [ ] **Step 3: Implement** `src/startup_agent/ports/cv_profile_extractor.py`:

```python
from abc import ABC, abstractmethod

from startup_agent.domain.applicant_profile import ApplicantProfile


class CvProfileExtractor(ABC):
    @abstractmethod
    def extract(self, cv_text: str) -> ApplicantProfile: ...
```

`src/startup_agent/adapters/profiling/prompt.py`:

```python
from startup_agent.domain.applicant_profile import ApplicantProfile

INSTRUCTIONS = (
    "You read a candidate's CV and extract ONLY these identity fields: "
    "first_name, last_name, location (city, country), and current_title "
    "(their most recent or current job title). "
    "Do NOT extract email, phone, or URLs. "
    'Return JSON: {"first_name": "", "last_name": "", "location": "", "current_title": ""}.'
)

_JUDGMENT = ("first_name", "last_name", "location", "current_title")


def to_profile(data: dict) -> ApplicantProfile:
    """Build an ApplicantProfile holding ONLY the LLM judgment fields (str-coerced)."""
    fields = {k: str(data.get(k) or "") for k in _JUDGMENT}
    return ApplicantProfile(**fields)
```

`src/startup_agent/adapters/profiling/claude_extractor.py`:

```python
import anthropic
from pydantic import BaseModel

from startup_agent.adapters.profiling.prompt import INSTRUCTIONS, to_profile
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.ports.cv_profile_extractor import CvProfileExtractor


class _Extraction(BaseModel):
    first_name: str = ""
    last_name: str = ""
    location: str = ""
    current_title: str = ""


class ClaudeProfileExtractor(CvProfileExtractor):
    def __init__(self, api_key: str = "", model: str = "claude-opus-4-8",
                 client: object | None = None) -> None:
        self._client = client or (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self._model = model

    def extract(self, cv_text: str) -> ApplicantProfile:
        message = self._client.messages.parse(
            model=self._model,
            max_tokens=400,
            system=[{"type": "text", "text": INSTRUCTIONS}],
            messages=[{"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nExtract the fields."}],
            output_format=_Extraction,
        )
        s = message.parsed_output
        return to_profile({"first_name": s.first_name, "last_name": s.last_name,
                           "location": s.location, "current_title": s.current_title})
```

Create empty `src/startup_agent/adapters/profiling/__init__.py` and `tests/adapters/profiling/__init__.py`.

- [ ] **Step 4: Run** `uv run pytest tests/adapters/profiling -v` → PASS. `uv run ruff check src tests`.
- [ ] **Step 5: Commit** `feat: CvProfileExtractor port + prompt + ClaudeProfileExtractor`.

---

### Task 3: OpenAIProfileExtractor

**Files:** Create `src/startup_agent/adapters/profiling/openai_extractor.py`; Test `tests/adapters/profiling/test_openai_extractor.py`.

- [ ] **Step 1: Write the failing test**:

```python
import json
from types import SimpleNamespace

from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"first_name": "Netanel", "last_name": "Sade",
                              "location": "Tel Aviv", "current_title": "Backend Engineer"})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_openai_extractor_returns_profile():
    client = _FakeClient()
    p = OpenAIProfileExtractor(client=client, model="gpt-4o").extract("MY CV")
    assert p.first_name == "Netanel" and p.current_title == "Backend Engineer"
    assert "MY CV" in str(client.chat.completions.calls[0])
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/adapters/profiling/openai_extractor.py`:

```python
import json

from startup_agent.adapters.profiling.prompt import INSTRUCTIONS, to_profile
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.ports.cv_profile_extractor import CvProfileExtractor


class OpenAIProfileExtractor(CvProfileExtractor):
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

    def extract(self, cv_text: str) -> ApplicantProfile:
        completion = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nExtract the fields."},
            ],
        )
        data = json.loads(completion.choices[0].message.content)
        return to_profile(data)
```

- [ ] **Step 4: Run** `uv run pytest tests/adapters/profiling -v` → PASS. `uv run ruff check src tests`.
- [ ] **Step 5: Commit** `feat: add OpenAIProfileExtractor`.

---

### Task 4: build_profile service (regex + optional LLM, graceful fallback)

**Files:** Create `src/startup_agent/services/profile_builder.py`; Test `tests/services/test_profile_builder.py`.

- [ ] **Step 1: Write the failing test**:

```python
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.services.profile_builder import build_profile

CV = "Netanel Sade\nEmail: a@b.com\nlinkedin.com/in/netanel-sade\n"


class _Extractor:
    def extract(self, cv_text):
        return ApplicantProfile(first_name="Netanel", last_name="Sade", location="Tel Aviv")


class _Boom:
    def extract(self, cv_text):
        raise RuntimeError("llm down")


def test_build_profile_regex_only_when_no_extractor():
    p = build_profile(CV, extractor=None)
    assert p.email == "a@b.com"
    assert p.linkedin_url == "https://linkedin.com/in/netanel-sade"
    assert p.first_name == "" and p.location == ""  # judgment fields blank


def test_build_profile_merges_llm_judgment_fields():
    p = build_profile(CV, extractor=_Extractor())
    assert p.email == "a@b.com"               # regex contact preserved
    assert p.first_name == "Netanel" and p.location == "Tel Aviv"  # llm judgment merged


def test_build_profile_llm_failure_falls_back_to_regex():
    p = build_profile(CV, extractor=_Boom())
    assert p.email == "a@b.com" and p.first_name == ""  # no exception, regex-only
```

- [ ] **Step 2: Run** `uv run pytest tests/services/test_profile_builder.py -v` → FAIL.
- [ ] **Step 3: Implement** `src/startup_agent/services/profile_builder.py`:

```python
import structlog

from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.ports.cv_profile_extractor import CvProfileExtractor
from startup_agent.profile.regex_extract import regex_extract

logger = structlog.get_logger(__name__)

_JUDGMENT = ("first_name", "last_name", "location", "current_title")


def build_profile(cv_text: str,
                  extractor: CvProfileExtractor | None = None) -> ApplicantProfile:
    """Regex fills contact fields; the LLM (if given) fills judgment fields.

    An LLM failure is logged and swallowed — the regex-only profile is returned.
    """
    profile = ApplicantProfile(**regex_extract(cv_text))
    if extractor is None:
        return profile
    try:
        judged = extractor.extract(cv_text)
    except Exception as exc:
        logger.warning(f"profile LLM extraction failed, using regex-only: {exc}")
        return profile
    update = {k: getattr(judged, k) for k in _JUDGMENT if getattr(judged, k)}
    return profile.model_copy(update=update)
```

Confirm `structlog` is already a dependency (it is — used across the project). If `tests/services/__init__.py` does not exist, create it empty.

- [ ] **Step 4: Run** `uv run pytest tests/services/test_profile_builder.py -v` → PASS. `uv run ruff check src tests`.
- [ ] **Step 5: Commit** `feat: build_profile service (regex + optional LLM, graceful fallback)`.

---

### Task 5: SQLite storage — profile table + save/get

**Files:** Modify `src/startup_agent/adapters/storage/schema.sql`, `src/startup_agent/adapters/storage/sqlite_repository.py`; Test `tests/adapters/storage/test_profile_repo.py`.

- [ ] **Step 1: Write the failing test** `tests/adapters/storage/test_profile_repo.py`:

```python
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.applicant_profile import ApplicantProfile


def test_profile_round_trip(tmp_path):
    repo = SQLiteJobRepository(str(tmp_path / "jobs.db"))
    repo.init_schema()
    assert repo.get_profile() is None
    repo.save_profile(ApplicantProfile(first_name="Netanel", email="a@b.com"))
    got = repo.get_profile()
    assert got.first_name == "Netanel" and got.email == "a@b.com"


def test_save_profile_overwrites(tmp_path):
    repo = SQLiteJobRepository(str(tmp_path / "jobs.db"))
    repo.init_schema()
    repo.save_profile(ApplicantProfile(first_name="A"))
    repo.save_profile(ApplicantProfile(first_name="B"))
    assert repo.get_profile().first_name == "B"
```

(If `tests/adapters/storage/__init__.py` is missing, create it empty.)

- [ ] **Step 2: Run** `uv run pytest tests/adapters/storage/test_profile_repo.py -v` → FAIL.
- [ ] **Step 3: Implement.** Append to `src/startup_agent/adapters/storage/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS profile (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    json       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Add to `SQLiteJobRepository` (mirror `save_preferences`/`get_preferences`, place right after them):

```python
    def save_profile(self, profile) -> None:
        self._conn.execute("DELETE FROM profile")
        self._conn.execute(
            "INSERT INTO profile (json, updated_at) VALUES (?, ?)",
            (profile.model_dump_json(), _now()),
        )
        self._conn.commit()

    def get_profile(self):
        from startup_agent.domain.applicant_profile import ApplicantProfile
        row = self._conn.execute(
            "SELECT json FROM profile ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return ApplicantProfile.model_validate_json(row["json"])
```

- [ ] **Step 4: Run** `uv run pytest tests/adapters/storage -v` → PASS. `uv run ruff check src tests`.
- [ ] **Step 5: Commit** `feat: profile table + save_profile/get_profile`.

---

### Task 6: deps — build_profile_extractor_from + get_profile_extractor

**Files:** Modify `api/deps.py`; Test `tests/api/test_get_profile_extractor.py`.

- [ ] **Step 1: Write the failing test**:

```python
from api import deps, llm_config


def test_build_profile_extractor_none_without_key():
    assert deps.build_profile_extractor_from("anthropic", "") is None


def test_build_profile_extractor_anthropic_and_openai():
    from startup_agent.adapters.profiling.claude_extractor import ClaudeProfileExtractor
    from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor
    assert isinstance(deps.build_profile_extractor_from("anthropic", "sk-x", "claude-opus-4-8"),
                      ClaudeProfileExtractor)
    assert isinstance(deps.build_profile_extractor_from("openai", "sk-x", "gpt-4o"),
                      OpenAIProfileExtractor)


def test_get_profile_extractor_prefers_in_memory_config():
    from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor
    llm_config.clear_config()
    llm_config.set_config("openai", "sk-mem", "gpt-4o")
    try:
        assert isinstance(deps.get_profile_extractor(), OpenAIProfileExtractor)
    finally:
        llm_config.clear_config()
```

- [ ] **Step 2: Run** `uv run pytest tests/api/test_get_profile_extractor.py -v` → FAIL.
- [ ] **Step 3: Implement** — add to `api/deps.py` (mirrors `get_suggester` exactly):

```python
def build_profile_extractor_from(provider: str, api_key: str, model: str = "", base_url: str = ""):
    """Build a CvProfileExtractor from raw config, or None when no key is given."""
    if not api_key:
        return None
    if (provider or "anthropic").lower() == "openai":
        from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor
        return OpenAIProfileExtractor(api_key=api_key, model=model or "gpt-4o", base_url=base_url)
    from startup_agent.adapters.profiling.claude_extractor import ClaudeProfileExtractor
    return ClaudeProfileExtractor(api_key=api_key, model=model or "claude-opus-4-8")


def get_profile_extractor():
    from api.llm_config import get_config
    cfg = get_config()
    if cfg is not None:
        return build_profile_extractor_from(cfg["provider"], cfg["api_key"], cfg.get("model", ""))
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        return build_profile_extractor_from("openai", settings.openai_api_key,
                                            settings.openai_model, settings.openai_base_url)
    return build_profile_extractor_from("anthropic", settings.anthropic_api_key, settings.llm_model)
```

- [ ] **Step 4: Run** `uv run pytest tests/api/test_get_profile_extractor.py -v && uv run pytest tests/api -q` → PASS. `uv run ruff check api tests`.
- [ ] **Step 5: Commit** `feat: build_profile_extractor_from + get_profile_extractor (mirrors ranker)`.

---

### Task 7: API routes — GET/PUT/POST /api/profile

**Files:** Create `api/routes/profile.py`; Modify `api/main.py`; Test `tests/api/test_profile_routes.py`.

- [ ] **Step 1: Write the failing test** `tests/api/test_profile_routes.py`:

```python
import io
from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.domain.applicant_profile import ApplicantProfile


def _pdf():
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


class _Extractor:
    def extract(self, cv_text):
        return ApplicantProfile(first_name="Netanel", last_name="Sade", location="Tel Aviv")


def test_profile_get_put_round_trip(client, settings):
    assert client.get("/api/profile").json()["first_name"] == ""
    resp = client.put("/api/profile", json={"first_name": "Netanel", "email": "a@b.com"})
    assert resp.status_code == 200
    assert client.get("/api/profile").json()["email"] == "a@b.com"


def test_profile_extract_no_cv_returns_400(client, settings):
    app.dependency_overrides[deps.get_profile_extractor] = lambda: None
    assert client.post("/api/profile/extract").status_code == 400


def test_profile_extract_regex_only_no_key(client, settings, monkeypatch):
    # CV text with contact info, no LLM key → contact filled, names blank, 200
    import api.routes.profile as mod
    monkeypatch.setattr(mod, "_cv_text_or_400",
                        lambda repo: "Netanel\nEmail: a@b.com\nlinkedin.com/in/netanel-sade")
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_profile_extractor] = lambda: None
    body = client.post("/api/profile/extract").json()
    assert body["email"] == "a@b.com"
    assert body["linkedin_url"] == "https://linkedin.com/in/netanel-sade"
    assert body["first_name"] == ""


def test_profile_extract_with_llm_fills_names(client, settings, monkeypatch):
    import api.routes.profile as mod
    monkeypatch.setattr(mod, "_cv_text_or_400", lambda repo: "Netanel Sade CV")
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_profile_extractor] = lambda: _Extractor()
    body = client.post("/api/profile/extract").json()
    assert body["first_name"] == "Netanel" and body["location"] == "Tel Aviv"
```

- [ ] **Step 2: Run** `uv run pytest tests/api/test_profile_routes.py -v` → FAIL (404).
- [ ] **Step 3: Implement** `api/routes/profile.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.services.profile_builder import build_profile

from api.deps import get_profile_extractor, get_settings

router = APIRouter()


def _cv_text_or_400(repo) -> str:
    cv = repo.get_cv()
    if cv is None:
        raise HTTPException(status_code=400, detail="No CV uploaded.")
    return cv["text"]


@router.get("/profile")
def get_profile(settings=Depends(get_settings)) -> ApplicantProfile:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    return repo.get_profile() or ApplicantProfile()


@router.put("/profile")
def put_profile(profile: ApplicantProfile, settings=Depends(get_settings)) -> dict:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.save_profile(profile)
    return {"status": "saved"}


@router.post("/profile/extract")
def extract_profile(extractor=Depends(get_profile_extractor),
                    settings=Depends(get_settings)) -> ApplicantProfile:
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    cv_text = _cv_text_or_400(repo)
    return build_profile(cv_text, extractor)
```

Modify `api/main.py` — add `profile` to the routes import and include it:

```python
from api.routes import cv, health, llm_config, preferences, profile, rate, results, run
```
```python
app.include_router(profile.router, prefix="/api")
```

- [ ] **Step 4: Run** `uv run pytest tests/api/test_profile_routes.py -v && uv run pytest -q` → green. `uv run ruff check src api tests`.
- [ ] **Step 5: Commit** `feat: GET/PUT/POST /api/profile(/extract)`.

---

### Task 8: Frontend — client API + ProfileForm + App wiring

**Files:** Modify `frontend/src/api/client.ts`, `frontend/src/App.tsx`, `frontend/src/styles/app.css`; Create `frontend/src/components/ProfileForm.tsx`.

- [ ] **Step 1: client.ts** — add (keep existing exports):

```ts
export interface ApplicantProfile {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  github_url: string;
  location: string;
  current_title: string;
}

export async function getProfile(): Promise<ApplicantProfile> {
  const resp = await fetch("/api/profile");
  if (!resp.ok) throw new Error(`Load profile failed (${resp.status})`);
  return resp.json();
}

export async function saveProfile(profile: ApplicantProfile): Promise<void> {
  const resp = await fetch("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!resp.ok) throw new Error(`Save profile failed (${resp.status})`);
}

export async function extractProfile(): Promise<ApplicantProfile> {
  const resp = await fetch("/api/profile/extract", { method: "POST" });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `Extract failed (${resp.status})`);
  }
  return resp.json();
}
```

- [ ] **Step 2: Create** `frontend/src/components/ProfileForm.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  type ApplicantProfile,
  extractProfile,
  getProfile,
  saveProfile,
} from "../api/client";

const FIELDS: { key: keyof ApplicantProfile; label: string }[] = [
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "linkedin_url", label: "LinkedIn URL" },
  { key: "github_url", label: "GitHub URL" },
  { key: "location", label: "Location" },
  { key: "current_title", label: "Current title" },
];

export function ProfileForm() {
  const [p, setP] = useState<ApplicantProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { getProfile().then(setP); }, []);

  async function extract() {
    setBusy(true); setErr(null); setSaved(false);
    try {
      const ex = await extractProfile();
      setP((cur) => ({ ...(cur as ApplicantProfile), ...ex }));
    } catch (e) { setErr(e instanceof Error ? e.message : "Extract failed"); }
    finally { setBusy(false); }
  }

  async function save() {
    if (!p) return;
    setErr(null);
    try { await saveProfile(p); setSaved(true); }
    catch (e) { setErr(e instanceof Error ? e.message : "Save failed"); }
  }

  if (!p) return null;

  return (
    <div className="profile-card">
      <h3 className="profile-title">Your application details</h3>
      <button className="autofill-btn" onClick={extract} disabled={busy}>
        {busy ? "Reading your CV…" : "Extract from CV"}
      </button>
      <p className="muted profile-hint">
        Email, phone and links fill automatically. Name &amp; location need an AI key
        (set it in AI scoring) — otherwise type them once.
      </p>
      <div className="profile-fields">
        {FIELDS.map(({ key, label }) => (
          <label key={key} className="profile-field">
            <span className="profile-field-label">{label}</span>
            <input
              value={p[key]}
              onChange={(e) => { setP({ ...p, [key]: e.target.value }); setSaved(false); }}
            />
          </label>
        ))}
      </div>
      <button className="primary" onClick={save}>{saved ? "Saved ✓" : "Save details"}</button>
      {err && <p className="error">{err}</p>}
    </div>
  );
}
```

- [ ] **Step 3: App.tsx** — render `<ProfileForm />` on the preferences screen, above the preferences form. Read the file; change the preferences-phase line:

```tsx
import { ProfileForm } from "./components/ProfileForm";
```
```tsx
        {phase === "preferences" && (
          <>
            <ProfileForm />
            <PreferencesForm onSaved={start} />
          </>
        )}
```

- [ ] **Step 4: app.css** — append:

```css
.profile-card { width: 100%; max-width: 560px; margin-bottom: 18px; text-align: left; }
.profile-title { font-size: 18px; font-weight: 800; color: var(--text); margin-bottom: 8px; }
.profile-hint { margin: 0 0 12px; }
.profile-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
.profile-field { display: flex; flex-direction: column; gap: 4px; }
.profile-field-label { font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; }
.profile-field input { padding: 7px 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; }
@media (max-width: 520px) { .profile-fields { grid-template-columns: 1fr; } }
```

- [ ] **Step 5: Build** `cd /Users/netanelsade/projects/startup-agent/frontend && npm run build` → clean. **Commit** `feat(web): applicant-profile details section`.

---

### Task 9: Frontend — per-job Apply panel + LinkedIn link

**Files:** Modify `frontend/src/components/JobCard.tsx`, `frontend/src/components/JobList.tsx`, `frontend/src/styles/app.css`.

- [ ] **Step 1: JobList.tsx** — fetch the profile once and pass it to each card:

```tsx
import { useEffect, useState } from "react";
import { type ApplicantProfile, getProfile, type JobMatch } from "../api/client";
import { JobCard } from "./JobCard";

export function JobList({ jobs }: { jobs: JobMatch[] }) {
  const [profile, setProfile] = useState<ApplicantProfile | null>(null);
  useEffect(() => { getProfile().then(setProfile); }, []);

  if (!jobs.length) return <p className="muted">No matching jobs.</p>;
  return (
    <div className="job-list">
      {jobs.map((j, i) => <JobCard key={i} job={j} profile={profile} />)}
    </div>
  );
}
```

- [ ] **Step 2: JobCard.tsx** — add an Apply toggle + panel. Read the current file; add the import, the new prop, state, the LinkedIn URL builder, copy helper, and the panel. Keep the existing rate logic intact:

```tsx
import { useState } from "react";
import { rateJob, type ApplicantProfile, type JobMatch } from "../api/client";

function initials(company: string): string {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2);
  return (words[0][0] + words[1][0]).toUpperCase();
}

function linkedinCompanyUrl(company: string): string {
  return `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(company)}`;
}

const PANEL_FIELDS: { key: keyof ApplicantProfile; label: string }[] = [
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "github_url", label: "GitHub" },
  { key: "location", label: "Location" },
  { key: "current_title", label: "Title" },
];

export function JobCard({ job, profile }: { job: JobMatch; profile: ApplicantProfile | null }) {
  const [j, setJ] = useState(job);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const meta = [j.company, j.location, j.age_label].filter(Boolean).join(" · ");

  async function rate() {
    setBusy(true); setErr(null);
    try {
      const r = await rateJob(j.job_id);
      setJ({ ...j, score: r.score, reason: r.reason, rated: true });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Rate failed");
    } finally {
      setBusy(false);
    }
  }

  async function copy(key: string, value: string) {
    try { await navigator.clipboard.writeText(value); setCopied(key); }
    catch { setCopied(`${key}:err`); }
    setTimeout(() => setCopied(null), 1200);
  }

  return (
    <div className="card">
      <div className="company-avatar" aria-hidden="true">{initials(j.company)}</div>
      <div className="card-body">
        <div className="card-top">
          <span className="card-title">{j.title}</span>
          <span className={`score${j.rated ? " score-ai" : ""}`}>{j.rated ? `✨ ${j.score}` : j.score}</span>
        </div>
        <div className="card-meta">{meta}</div>
        {j.reason && <div className="reason">{j.reason}</div>}
        <div className="card-actions">
          <a className="apply" href={j.url} target="_blank" rel="noreferrer">Open application →</a>
          <button className="rate-btn" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide apply kit" : "Apply"}
          </button>
          {!j.rated && (
            <button className="rate-btn" onClick={rate} disabled={busy}>
              {busy ? "Rating…" : "✨ Rate"}
            </button>
          )}
        </div>
        {open && (
          <div className="apply-panel">
            <a className="li-link" href={linkedinCompanyUrl(j.company)} target="_blank" rel="noreferrer">
              View {j.company} on LinkedIn ↗
            </a>
            {!profile || PANEL_FIELDS.every((f) => !profile[f.key]) ? (
              <p className="muted">No details yet — fill "Your application details" on the preferences screen.</p>
            ) : (
              <div className="apply-fields">
                {PANEL_FIELDS.filter((f) => profile[f.key]).map(({ key, label }) => (
                  <div key={key} className="apply-row">
                    <span className="apply-row-label">{label}</span>
                    <span className="apply-row-val">{profile[key]}</span>
                    <button className="copy-btn" onClick={() => copy(key, profile[key])}>
                      {copied === key ? "Copied ✓" : copied === `${key}:err` ? "⚠" : "Copy"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: app.css** — append:

```css
.apply-panel { margin-top: 12px; padding-top: 10px; border-top: 1px solid #eee; display: flex; flex-direction: column; gap: 8px; }
.li-link { color: var(--accent); font-size: 13px; font-weight: 600; }
.apply-fields { display: flex; flex-direction: column; gap: 6px; }
.apply-row { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.apply-row-label { width: 80px; color: var(--muted); font-weight: 700; flex-shrink: 0; }
.apply-row-val { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.copy-btn { background: var(--accent-soft); color: var(--accent); border: 1px solid #c7d2fe; border-radius: 6px; padding: 3px 10px; font-size: 12px; cursor: pointer; flex-shrink: 0; }
```

- [ ] **Step 4: Build** `cd /Users/netanelsade/projects/startup-agent/frontend && npm run build` → clean (no TS errors).
- [ ] **Step 5: Commit** `feat(web): per-job apply panel with copy + LinkedIn link`.

---

### Task 10: Live smoke + checkpoint (NO MERGE — user reviews first)

- [ ] **Step 1:** Backend suite + lint: `uv run pytest -q && uv run ruff check src api tests` → green.
- [ ] **Step 2:** Frontend build clean: `cd frontend && npm run build`.
- [ ] **Step 3:** `make dev`; verify on the preferences screen: "Your application details" shows; "Extract from CV" (with no key) fills email/phone/LinkedIn/GitHub from the real CV and leaves name/location blank; editing + Save persists (reload keeps values). On results, each job's "Apply" reveals the saved fields with working Copy buttons, a "View company on LinkedIn" link, and "Open application →".
- [ ] **Step 4:** **STOP. Do NOT merge to `main`.** Report status to the user and let them try the running app. Merge `phase-12/applicant-profile` → `main` ONLY after the user explicitly approves.

> **Checkpoint:** Applicant profile + apply helper complete on `phase-12/applicant-profile`. Regex baseline works without a key; LLM enhances name/location/title when configured; per-job copy + LinkedIn link; nothing auto-submitted. Awaiting user's keep/discard decision before merge.

---

## Self-Review Notes

- **Spec coverage:** 8 fields split regex/LLM §2 → Task 1 (regex+model) + Task 2 (`to_profile` judgment-only); regex+optional-LLM with graceful fallback §3 → Task 4 (`build_profile` try/except); domain/storage/deps §4 → Tasks 1,5,6; routes incl. no-CV 400 and no-key 200 §5/§7 → Task 7 tests; ProfileForm section + per-job Apply panel + LinkedIn company-search link §6 → Tasks 8,9; error handling (no-CV 400, no-key 200, LLM failure regex-only, copy-fail state) §7 → Tasks 4,7,9; offline testing §8 → mocked extractors throughout; workflow no-merge-until-approval §9 → Task 10 Step 4; scope §10 respected (no cover letters/salary/extension/tracking).
- **Placeholder scan:** none — concrete code/commands throughout.
- **Type consistency:** `ApplicantProfile` (8 str fields) consistent across domain, port, adapters, service, repo, routes, and the TS interface. `CvProfileExtractor.extract(cv_text) -> ApplicantProfile`; `regex_extract(cv_text) -> dict`; `build_profile(cv_text, extractor=None) -> ApplicantProfile`; `to_profile(data) -> ApplicantProfile`; `build_profile_extractor_from(provider, api_key, model="", base_url="")` + `get_profile_extractor()`; routes `/profile`, `/profile/extract`; TS `getProfile/saveProfile/extractProfile`. The four judgment-field names (first_name/last_name/location/current_title) and four contact-field names (email/phone/linkedin_url/github_url) are consistent everywhere. `JobCard` now takes `{job, profile}` and `JobList` supplies `profile` — both updated in Task 9.
