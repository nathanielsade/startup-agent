# CV → Preferences Auto-fill — Design Spec

**Date:** 2026-06-20
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

An "✨ Auto-fill from CV" button on the Preferences screen: the LLM reads the stored
CV, suggests the preference fields a CV can actually reveal, **pre-fills the form**,
and the user reviews/edits before saving. Never auto-applied. Uses the existing
provider-pluggable LLM config (key from the in-memory UI store or `.env`).

## 2. What it fills (CV-inferable only)

The suggester returns ONLY fields a CV genuinely reveals:
- **max_years** — a sensible ceiling derived from total experience (e.g. ~1 yr of
  experience → suggests `3`).
- **roles** — domain(s) from the CV, drawn from the app's vocabulary
  (`backend / frontend / full-stack / ai / data / devops / security`).
- **seniority** — from `junior / mid / senior`.
- **title_include** — relevant title keywords (e.g. `engineer`, `developer`).

It leaves the **pure-preference** fields — `districts`, `include_remote`,
`posted_within_days`, `exclude` (title-exclude) — at the user's current values; a CV
doesn't reveal those choices. The suggestion is **merged** onto the current form:
only the inferable fields change. The user edits anything and then uses the existing
Save. Nothing is saved automatically.

## 3. Architecture (mirrors the ranker; fits existing ports-&-adapters layers)

- **port** `ports/cv_suggester.py`: `CvPreferenceSuggester.suggest(cv_text: str) ->
  Preferences`.
- **adapters** `adapters/suggesting/`:
  - `ClaudeCvSuggester` — Anthropic `messages.parse` with a structured schema
    `{max_years: int|null, roles: [str], seniority: [str], title_include: [str]}`,
    validated into a `Preferences` (other fields left at defaults).
  - `OpenAICvSuggester` — OpenAI JSON output, same schema.
  - A shared suggest-prompt (instructions + the allowed role/seniority vocab + the
    CV text). Both take an injectable `client` for offline tests.
- **deps** `api/deps.py`: `build_suggester_from(provider, api_key, model, base_url)`
  + `get_suggester()` — built from the **same** configured provider/key as
  `get_ranker` (in-memory store first, then `.env`); returns `None` when no key.
- **api** `api/routes/preferences.py`: add `POST /api/preferences/suggest` →
  loads the stored CV text + current preferences → `suggester.suggest(cv_text)` →
  returns a `Preferences` whose inferable fields are filled and whose
  pure-preference fields equal the current saved prefs (so the frontend can merge
  safely). `400` if no suggester configured or no CV.
- **frontend**:
  - `api/client.ts`: `suggestPreferences() -> Preferences`.
  - `PreferencesForm`: an "✨ Auto-fill from CV" button (near the title). On click →
    `suggestPreferences()` → **merge only the inferable fields** (`max_years`,
    `roles`, `seniority`, `title_include`) into the form state, leaving
    `districts`/`include_remote`/`posted_within_days`/`exclude` as the user had them
    → user reviews/edits → existing "Save & Find jobs". Button disabled with a hint
    ("add a key in AI scoring below") when no LLM is configured (checks
    `getLlmConfig()`); busy + error states.

## 4. Data flow

```
Preferences screen → "✨ Auto-fill from CV"
  → POST /api/preferences/suggest
       → load CV text + current prefs
       → suggester.suggest(cv_text) → {max_years, roles, seniority, title_include}
       → return Preferences (inferable filled; other fields = current)
  → form merges ONLY the inferable fields → user reviews/edits → Save
```

## 5. Error handling

- **No LLM configured** → `get_suggester()` is `None`; the route returns `400`
  ("No LLM configured"); the button is disabled with a hint.
- **No CV stored** → `400` ("No CV uploaded"). (Rare — the screen is post-upload.)
- **Malformed LLM output** → validated against the `{max_years, roles, seniority,
  title_include}` schema; on failure the route returns `502`/error and the form is
  left unchanged with a notice. Out-of-vocab roles/seniority returned by the model
  are dropped to the known options.
- **LLM call failure** → surfaced as an error on the button; the form is unchanged.

## 6. Testing (offline)

- **Suggesters:** `ClaudeCvSuggester` + `OpenAICvSuggester` with **mocked clients** →
  CV text in → the 4 fields parsed into a `Preferences`; out-of-vocab values dropped.
- **Provider selection:** `get_suggester()` returns the right impl per provider,
  `None` without a key.
- **API:** `POST /api/preferences/suggest` via TestClient with a mocked suggester
  (returns a `Preferences`; no-key → 400; no-CV → 400); the response keeps the
  current pure-preference values.
- **Frontend:** the button calls the API and merges ONLY the inferable fields
  (districts/remote/etc. untouched); disabled state when unconfigured.

All backend tests run offline (mocked suggesters; no key, no network).

## 7. Scope

**In:** the "✨ Auto-fill from CV" button, `POST /api/preferences/suggest`,
provider-pluggable suggesters (Claude + OpenAI), merge-not-overwrite of the
CV-inferable fields, review-before-save, reuse of the existing LLM key config.

**Out (deferred):** suggesting pure-preference fields (districts/remote/freshness);
auto-saving without review; a separate key/provider for suggestions; suggesting from
anything other than the stored CV.

## 8. Visual design

The button matches the Light-SaaS style: a subtle indigo-outline "✨ Auto-fill from
CV" button near the "Your preferences" title. While running it shows a spinner;
on success the relevant chips/inputs visibly update (the merged fields); when no LLM
is configured it's disabled with a small muted hint pointing at the AI-scoring panel
below.
