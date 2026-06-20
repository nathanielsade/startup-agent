# Applicant Profile + Apply Helper — Design Spec

**Date:** 2026-06-20
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

A saved **applicant profile** — the standard fields every job-application form asks
for — extracted from the user's CV once, editable, and one-click-copyable on every
job, alongside a LinkedIn company link and the existing "open application" link.

v1 removes the repetitive retyping of identity/contact fields. It does **not** draft
cover letters and **never** submits anything: the user copies the fields and submits
on the real ATS page themselves. The user is the submit gate by construction.

## 2. The profile fields

| Field | Filled by |
|---|---|
| `email`, `phone`, `linkedin_url`, `github_url` | **regex** — deterministic, no API key, works today |
| `first_name`, `last_name`, `location`, `current_title` | **LLM** — when a key is configured; left blank otherwise |

These are the fields standard application forms request. No salary, no screening
answers, no cover letter (all deferred).

## 3. Extraction — regex baseline + optional LLM

Two independent extractors merged by a service:

- **Regex** (`src/startup_agent/profile/regex_extract.py`): a pure
  `regex_extract(cv_text: str) -> dict` returning the four pattern fields:
  - `email`  — `[\w.+-]+@[\w-]+\.[\w.-]+` (first match)
  - `phone`  — a phone-shaped run `(\+?\d[\d\-\s().]{7,}\d)`, whitespace-collapsed
  - `linkedin_url` — first `linkedin\.com/in/[\w\-%./]+`, normalized to `https://…`
  - `github_url`   — first `github\.com/[\w\-]+`, normalized to `https://…`
  Missing fields are simply absent from the dict. Deterministic; no network.

- **LLM** (`CvProfileExtractor` port + adapters, mirrors the suggester): returns the
  four judgment fields `{first_name, last_name, location, current_title}`.
  - `ports/cv_profile_extractor.py`: `CvProfileExtractor.extract(cv_text: str) -> ApplicantProfile`.
  - `adapters/profiling/prompt.py`: `INSTRUCTIONS` + `to_profile(data: dict) -> ApplicantProfile`
    (keeps only the judgment fields; tolerates missing keys; coerces to str).
  - `adapters/profiling/claude_extractor.py`: `ClaudeProfileExtractor` (Anthropic
    `messages.parse`, `_Extraction` pydantic schema, `parsed_output`).
  - `adapters/profiling/openai_extractor.py`: `OpenAIProfileExtractor`
    (`chat.completions` JSON object). Both take an injectable `client` for offline tests.

- **Service** (`src/startup_agent/services/profile_builder.py`):
  `build_profile(cv_text: str, extractor: CvProfileExtractor | None = None) -> ApplicantProfile`.
  Always runs regex for the contact fields. If `extractor` is not None, calls it for
  the judgment fields and merges them in; **if the LLM call raises, it is caught and
  the regex-only profile is returned** (logged, never propagated as a 500). Returns one
  `ApplicantProfile`.

## 4. Domain + storage + deps

- **Domain** `src/startup_agent/domain/applicant_profile.py`: `ApplicantProfile`
  pydantic v2 model, all fields `str = ""` defaults:
  `first_name, last_name, email, phone, linkedin_url, github_url, location, current_title`.
- **Storage** `SQLiteJobRepository`: a `profile` table (single row, like preferences)
  with `save_profile(profile: ApplicantProfile) -> None` and
  `get_profile() -> ApplicantProfile | None`, plus `init_schema()` creating the table.
- **Deps** `api/deps.py`: `build_profile_extractor_from(provider, api_key, model="", base_url="")`
  + `get_profile_extractor()` — built from the **same** configured provider/key as
  `get_ranker`/`get_suggester` (in-memory store first, then `.env`); returns `None`
  when no key. Mirrors the existing `get_suggester` exactly.

## 5. API (mirrors preferences)

`api/routes/profile.py`:
- `GET /api/profile` → stored `ApplicantProfile` or a default empty one.
- `PUT /api/profile` → saves the posted `ApplicantProfile`; `{"status": "saved"}`.
- `POST /api/profile/extract` → loads the stored CV text, runs
  `build_profile(cv_text, get_profile_extractor())`, returns the resulting
  `ApplicantProfile`. `400` only if **no CV** is uploaded. With no LLM key it still
  succeeds, returning regex-filled contact fields and blank name/location/title.

The extract route **does not** persist — it returns fresh values for the form; the
user reviews/edits and then `PUT`s to save.

## 6. Frontend

- **`frontend/src/api/client.ts`**: `ApplicantProfile` type; `getProfile()`,
  `saveProfile(p)`, `extractProfile()`.
- **`frontend/src/components/ProfileForm.tsx`**: a "Your application details" section
  rendered on the post-upload screen (sibling to `PreferencesForm`). An
  **"Extract from CV"** button (always enabled — regex works without a key; a muted
  hint notes that name/location need a key), editable text inputs for all eight fields,
  busy/error states, and a **Save** button (`saveProfile`). On extract it fills the
  form fields; the user edits any blanks (e.g. name with no key) once.
- **`frontend/src/components/JobCard.tsx`**: an **"Apply"** toggle revealing a panel
  that shows each saved profile field with a **copy button**
  (`navigator.clipboard.writeText`), a **"View company on LinkedIn"** link
  (`https://www.linkedin.com/search/results/companies/?keywords=<encoded company>`,
  built client-side from `job.company`), and the existing **"Open application →"**
  link (`job.url`). The saved profile is fetched **once** in the results view
  (`JobList`) via `getProfile()` and passed down to each `JobCard` as a prop, so the
  panel renders the current saved fields without per-card fetches.
- **`frontend/src/styles/app.css`**: styles for the details section, copy buttons, and
  the apply panel, matching the Light-SaaS look.

## 7. Error handling

- **No CV** → `POST /api/profile/extract` returns `400` ("No CV uploaded.").
- **No LLM key** → extraction still returns `200` with regex contact fields filled and
  judgment fields blank (the core no-key value).
- **LLM call failure** → caught in `build_profile`; regex-only profile returned, `200`.
- **Empty clipboard / copy unsupported** → the copy button shows a brief "copy failed"
  state; the field text is always visible to select manually.

## 8. Testing (offline)

- **Regex** (`regex_extract`): a CV-text fixture with email/phone/LinkedIn/GitHub →
  all four extracted and normalized; a bare CV text → those keys absent.
- **Service** (`build_profile`): regex-only (no extractor) → contact fields filled,
  name/location blank; with a mock extractor → judgment fields merged in; a mock
  extractor that raises → regex-only profile returned (no exception).
- **LLM adapters**: `ClaudeProfileExtractor` + `OpenAIProfileExtractor` with mocked
  clients → judgment fields parsed into an `ApplicantProfile`; CV text reaches the prompt.
- **Deps**: `get_profile_extractor()` returns the right impl per provider, `None`
  without a key.
- **API**: `GET`/`PUT` round-trip; `POST /api/profile/extract` via TestClient with no
  LLM override (contact filled, names blank, 200), with a mocked extractor (names
  filled), and with no CV (400).
- **Frontend**: the LinkedIn URL builder encodes the company name; the Apply panel
  renders the saved fields with copy buttons; "Extract from CV" calls the API and fills
  the form.

All backend tests run offline (mocked extractors; no key, no network).

## 9. Workflow constraint (user-requested)

The user wants to **see the feature running before deciding whether to keep it**.
Implementation happens on branch `phase-12/applicant-profile`; after the build, the app
is run locally for the user to try. **The branch is merged to `main` only on the user's
explicit approval** — nothing lands in `main` beforehand.

## 10. Scope

**In:** `ApplicantProfile` model + storage, regex + optional-LLM extraction with
graceful LLM fallback, `GET`/`PUT`/`POST /api/profile/extract`, the "Your application
details" section, the per-job Apply panel with copy buttons + LinkedIn company-search
link + open-application, offline tests.

**Out (deferred):** cover-letter / "why this company" drafting; salary or screening-
question answers; browser-extension form-fill; application status tracking; guessing the
exact `linkedin.com/company/<slug>` URL (search link is used instead).
