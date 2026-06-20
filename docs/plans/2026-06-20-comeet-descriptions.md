# Comeet Descriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Enrich Comeet jobs with real descriptions by fetching each position's hosted page (concurrently) and extracting the embedded description, so ~30 Comeet companies match as well as the other ATSes.

**Architecture:** Add a pure `extract_description(html)` helper and an injectable page-fetcher to `ComeetAdapter`; after building the position `Job`s, fetch each one's `url_comeet_hosted_page` in a bounded thread pool and attach the cleaned description. One adapter file; no interface/factory changes.

**Tech Stack:** Python 3.13, httpx, `concurrent.futures.ThreadPoolExecutor`, pytest. All tests offline (captured fixture + injected fake page-fetcher).

**Repo discipline:** Work ONLY in `/Users/netanelsade/projects/startup-agent`; never touch `/Users/netanelsade/conifers`. Branch `phase-10/comeet-descriptions`. Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File structure
```
src/startup_agent/adapters/ats/comeet.py   MODIFY: extract_description() + concurrent enrichment
tests/adapters/ats/test_comeet.py          MODIFY: stub fetch_page (offline) + new description tests
spike/fixtures/comeet_hosted_page.html     (already captured — real hosted page with a description)
spike/fixtures/comeet_aqua.json            (existing — positions list with url_comeet_hosted_page)
```

---

### Task 1: `extract_description(html)` helper

**Files:** Modify `src/startup_agent/adapters/ats/comeet.py`; Test `tests/adapters/ats/test_comeet.py` (append).

- [ ] **Step 1: Write the failing test** (append to `tests/adapters/ats/test_comeet.py`)

```python
from pathlib import Path

from startup_agent.adapters.ats.comeet import extract_description

HOSTED = Path("spike/fixtures/comeet_hosted_page.html")


def test_extract_description_from_real_hosted_page():
    desc = extract_description(HOSTED.read_text())
    assert desc is not None
    assert len(desc) > 100
    assert "Aqua" in desc          # real content from the fixture
    assert "<" not in desc         # HTML tags stripped
    assert "&nbsp;" not in desc    # entities unescaped


def test_extract_description_none_when_absent():
    assert extract_description("<html><body>no description here</body></html>") is None
    assert extract_description("") is None
```

- [ ] **Step 2: Run** `uv run pytest tests/adapters/ats/test_comeet.py::test_extract_description_from_real_hosted_page -v` → FAIL (no `extract_description`).
- [ ] **Step 3: Implement** — add to the top of `src/startup_agent/adapters/ats/comeet.py` (after the imports; add `import html as _html`, `import json`, `import re`):

```python
import html as _html
import json
import re

_DESC_RE = re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def extract_description(page_html: str) -> str | None:
    """Pull the embedded JSON "description" out of a Comeet hosted page → plain text."""
    if not page_html:
        return None
    match = _DESC_RE.search(page_html)
    if not match:
        return None
    try:
        raw = json.loads('"' + match.group(1) + '"')  # unescape the JSON string
    except (ValueError, json.JSONDecodeError):
        return None
    text = _WS_RE.sub(" ", _html.unescape(_TAG_RE.sub(" ", raw))).strip()
    return text or None
```

- [ ] **Step 4: Run** `uv run pytest tests/adapters/ats/test_comeet.py -k extract_description -v` → 2 passed.
- [ ] **Step 5: Commit**

```bash
git add src/startup_agent/adapters/ats/comeet.py tests/adapters/ats/test_comeet.py spike/fixtures/comeet_hosted_page.html
git commit -m "feat: extract_description() for Comeet hosted pages" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Concurrent description enrichment in ComeetAdapter

**Files:** Modify `src/startup_agent/adapters/ats/comeet.py`, `tests/adapters/ats/test_comeet.py`.

- [ ] **Step 1: Write the failing tests** (append to `tests/adapters/ats/test_comeet.py`)

```python
def test_comeet_attaches_descriptions_from_hosted_pages():
    payload = [
        {"uid": "P1", "name": "Backend Engineer", "url_active_page": "https://x/1",
         "url_comeet_hosted_page": "https://www.comeet.com/jobs/acme/9/be/P1",
         "location": {"name": "Tel Aviv"}, "time_updated": "2026-01-01T00:00:00+00:00"},
        {"uid": "P2", "name": "Data Engineer", "url_active_page": "https://x/2",
         "url_comeet_hosted_page": "https://www.comeet.com/jobs/acme/9/de/P2",
         "location": {"name": "Tel Aviv"}, "time_updated": "2026-01-01T00:00:00+00:00"},
    ]
    pages = {
        "https://www.comeet.com/jobs/acme/9/be/P1":
            '<script>{"description":"Build \\u003cb\\u003ebackend\\u003c/b\\u003e services and APIs."}</script>',
        "https://www.comeet.com/jobs/acme/9/de/P2":
            '<script>{"description":"Own the data pipelines."}</script>',
    }
    adapter = ComeetAdapter(fetch_json=lambda url: payload, fetch_page=lambda url: pages[url])
    jobs = adapter.fetch_jobs(Company(name="Acme", ats_type=AtsType.COMEET, ats_token="9:tok"))
    by_title = {j.title: j for j in jobs}
    assert "backend services" in by_title["Backend Engineer"].description
    assert "<b>" not in by_title["Backend Engineer"].description   # tags stripped
    assert by_title["Data Engineer"].description == "Own the data pipelines."


def test_comeet_description_failure_is_graceful():
    payload = [
        {"uid": "P1", "name": "Backend Engineer", "url_active_page": "https://x/1",
         "url_comeet_hosted_page": "https://ok", "location": {"name": "Tel Aviv"}},
        {"uid": "P2", "name": "Data Engineer", "url_active_page": "https://x/2",
         "url_comeet_hosted_page": "https://boom", "location": {"name": "Tel Aviv"}},
    ]

    def fetch_page(url):
        if url == "https://boom":
            raise RuntimeError("network down")
        return '<script>{"description":"Good description."}</script>'

    adapter = ComeetAdapter(fetch_json=lambda url: payload, fetch_page=fetch_page)
    jobs = adapter.fetch_jobs(Company(name="Acme", ats_type=AtsType.COMEET, ats_token="9:tok"))
    by_title = {j.title: j for j in jobs}
    assert by_title["Backend Engineer"].description == "Good description."
    assert by_title["Data Engineer"].description is None   # failed page → no desc, still returned
    assert len(jobs) == 2
```

- [ ] **Step 2: Update the EXISTING Comeet tests to stay offline** — the existing tests in `tests/adapters/ats/test_comeet.py` construct `ComeetAdapter(fetch_json=...)` without a `fetch_page`; once `fetch_page` defaults to a real HTTP GET, they'd hit the network. Add `fetch_page=lambda url: ""` to those existing `ComeetAdapter(...)` constructions (a `""` page → `extract_description` returns `None`, so their behavior — jobs with `description=None` — is unchanged). Leave their assertions intact.

- [ ] **Step 3: Run** `uv run pytest tests/adapters/ats/test_comeet.py -v` → the two new tests FAIL (ComeetAdapter has no `fetch_page` param yet).
- [ ] **Step 4: Implement** — update `src/startup_agent/adapters/ats/comeet.py`. Add imports + a default page fetcher + concurrency:

```python
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

_MAX_WORKERS = 8
_PAGE_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _default_fetch_page(url: str) -> str:
    resp = httpx.get(url, timeout=10.0, follow_redirects=True, headers={"User-Agent": _PAGE_UA})
    resp.raise_for_status()
    return resp.text
```

Then change `ComeetAdapter`:

```python
class ComeetAdapter(ATSAdapter):
    ats_type = AtsType.COMEET

    def __init__(self, fetch_json: JsonFetcher | None = None,
                 fetch_page: "Callable[[str], str] | None" = None) -> None:
        self._fetch = fetch_json or HttpJsonFetcher()
        self._fetch_page = fetch_page or _default_fetch_page

    def fetch_jobs(self, company: Company) -> list[Job]:
        token_field = company.ats_token or ""
        if ":" not in token_field:
            logger.warning("comeet_missing_uid_token", company=company.name)
            return []
        uid, token = token_field.split(":", 1)
        payload = self._fetch(_BASE.format(uid=uid, token=token))
        jobs: list[Job] = []
        job_pages: list[tuple[Job, str]] = []
        for raw in payload:  # Comeet returns a top-level list
            try:
                location = raw.get("location") or {}
                job = Job(
                    company_id=company.id_hash,
                    ats_job_id=str(raw["uid"]),
                    title=raw["name"],
                    url=(raw.get("url_active_page") or raw.get("position_url")
                         or raw.get("url_comeet_hosted_page")),
                    location=location.get("name"),
                    description=None,
                    posted_at=parse_dt(raw.get("time_updated")),
                )
            except Exception as error:
                logger.warning("skip_bad_job", company=company.name, ats="comeet", error=str(error))
                continue
            jobs.append(job)
            hosted = raw.get("url_comeet_hosted_page") or raw.get("position_url")
            if hosted:
                job_pages.append((job, hosted))

        self._enrich_descriptions(company, job_pages)
        return jobs

    def _enrich_descriptions(self, company: Company,
                             job_pages: list[tuple[Job, str]]) -> None:
        if not job_pages:
            return
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(self._fetch_page, url): job for job, url in job_pages}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    desc = extract_description(future.result())
                except Exception as error:
                    logger.warning("comeet_description_failed", company=company.name,
                                   job=job.title, error=str(error))
                    continue
                if desc:
                    job.description = desc
```

- [ ] **Step 5: Run** `uv run pytest tests/adapters/ats/test_comeet.py -v` → all pass (new + existing). Full suite `uv run pytest -q` → green. `uv run ruff check src tests`.
- [ ] **Step 6: Commit**

```bash
git add src/startup_agent/adapters/ats/comeet.py tests/adapters/ats/test_comeet.py
git commit -m "feat: ComeetAdapter fetches hosted-page descriptions concurrently" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Live smoke + checkpoint

- [ ] **Step 1:** Full suite + lint: `uv run pytest -q && uv run ruff check src tests` → green.
- [ ] **Step 2: Live check** — confirm a real Comeet company now yields descriptions:

```bash
cd /Users/netanelsade/projects/startup-agent
uv run python - <<'PY'
import json
from startup_agent.adapters.ats.comeet import ComeetAdapter
from startup_agent.domain.models import Company, AtsType
tok = next(t for t in json.load(open("spike/fixtures/comeet_tokens.json")) if "Aqua" in t["name"])
jobs = ComeetAdapter().fetch_jobs(Company(name="Aqua", ats_type=AtsType.COMEET, ats_token=tok["ats_token"]))
withdesc = [j for j in jobs if j.description]
print(f"{len(jobs)} jobs, {len(withdesc)} with descriptions")
if withdesc:
    print("sample:", withdesc[0].title, "->", (withdesc[0].description or "")[:140])
PY
```
Expected: most/all jobs now have non-empty descriptions.

- [ ] **Step 3:** Merge `phase-10/comeet-descriptions` → `main`.

> **Checkpoint:** Comeet jobs now carry descriptions → better embedding + LLM matching for those ~30 companies.

---

## Self-Review Notes

- **Spec coverage:** finding (hosted page has description) §2 → fixture + Task 1; extraction helper §5 → Task 1 `extract_description`; concurrent enrichment in the adapter §3/§4/§5 → Task 2 `_enrich_descriptions` (ThreadPoolExecutor, pool 8, injectable `fetch_page`); graceful per-job failure §7 → Task 2 `test_comeet_description_failure_is_graceful` + try/except; offline tests §8 → fixture + injected `fetch_page` + the existing-test stub fix (Task 2 Step 2); perf note §10 → bounded pool. No interface/factory change (matches §5).
- **Placeholder scan:** none — concrete code/commands throughout.
- **Type consistency:** `extract_description(html: str) -> str | None` used in Task 1 + Task 2. `ComeetAdapter(fetch_json=None, fetch_page=None)` consistent across new tests, existing-test fix, and impl. `_default_fetch_page(url) -> str`, `_enrich_descriptions(company, job_pages)`, `_MAX_WORKERS` consistent. `Job.description` mutated post-construction (Job is a non-frozen pydantic model — assignment is valid).
