# Per-User Preferences — Design Spec

**Date:** 2026-06-19
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

Replace the hardcoded, global `preferences.yaml` rules with a **structured,
per-user preferences profile** that the user defines — manually, or via an LLM
that reads their CV and proposes preferences they approve/edit. Those
preferences then drive the whole filter + ranking pipeline. The result: the tool
is no longer hardcoded to one person — anyone can make it match *their* criteria.

## 2. User model — generic single-profile

No accounts, no login. The app holds **one active profile**: a CV + one
preferences record. Nothing is hardcoded to a specific person. The existing
static `data/preferences.yaml` becomes only the **initial default seed**; the
live preferences are a structured record stored in the database and edited
through the UI. (True multi-user with accounts is explicitly out of scope.)

## 3. Preference fields

| Field | Type | Strictness | Source of truth in a job |
|---|---|---|---|
| Districts | multi-select: Center / North / South / Jerusalem | **hard** (drop) | job location string |
| Remote acceptance | toggle (+ foreign-remote rule) | **hard** | job location string |
| Max experience years | integer | **hard** (drop) | job **description** (regex for "N+ years") |
| Employment type | set: full-time / contract / part-time / internship | **hard** | structured field where the ATS provides it; else description |
| Posted within | integer days | **hard** | job `posted_at` |
| Company type | set: startup / enterprise | **hard** | our company metadata |
| Title include / exclude | keyword lists | **hard** | job title |
| Role / domain | multi-select: backend / frontend / full-stack / AI-ML / data / devops / security | **soft** (rank) | title + description (+ LLM when on) |
| Seniority | multi-select: junior / mid / senior | **soft** (rank) | title + description (+ LLM when on) |

Strictness is **fixed by the system** (not user-toggled). **Hard** = drop the
job. **Soft** = adjust the ranking score, never drop. **Unset fields filter
nothing** (a blank district list drops nothing on location, etc.).

## 4. Two ways to create preferences

- **Manual (always available, no API key):** the Preferences screen — chips for
  multi-selects, a slider for max-years, toggles, keyword inputs.
- **Auto-fill from CV (optional, needs API key):** an "✨ Auto-fill from my CV"
  action sends the stored CV text to the LLM, which returns a *suggested*
  preferences object (e.g. infers "1–2 years, backend/AI, junior–mid"). The form
  is **pre-filled** with the suggestion; the user **reviews, edits, and
  approves** before it is saved. Never applied silently.

## 5. How preferences drive matching

1. **Hard preferences → deterministic prefilter.** `passes_prefilter(job, prefs)`
   is generalized: the existing title/location rules plus new rules for
   max-years (description regex), employment type, freshness (`posted_at`),
   company type, and generalized districts. A job failing any *set* hard rule is
   dropped before embedding.
2. **Soft preferences → score adjustment.** After cosine similarity produces a
   base score, a `soft_score(job, prefs)` step adds a small bonus when
   role/domain matches and a small penalty when seniority is off, then results
   are re-sorted. Jobs are reordered, never dropped, by soft prefs.
3. **LLM ranking (when enabled) → prompt injection.** When the `--llm` path runs,
   the full preferences object is rendered into the Claude prompt ("candidate
   wants junior–mid backend/AI roles, ≤3 years, full-time, Center/remote") so the
   model judges true fit. (The LLM ranker already exists; this adds prefs to its
   context.)

## 6. Architecture (fits existing ports-&-adapters layers)

- **domain:** expand `Preferences` (in `domain/preferences.py`) into the
  structured model in §3 (districts list, remote bool, max_years int, employment
  set, posted_within_days int, company_types set, title include/exclude lists,
  roles set, seniority set). Provide sensible defaults so an empty profile is valid.
- **engine:**
  - `PreferencesRepository` behavior on the existing repo (a `preferences`
    table; `save_preferences` / `get_preferences`, single row). Seed from
    `preferences.yaml` on first use if empty.
  - generalize `matching/prefilter.py` (all hard rules) and add
    `matching/soft_score.py` (the soft adjustment); `SimilarityMatchingService`
    applies base cosine + soft adjustment.
  - `matching/experience.py` — `required_years(description) -> int | None` regex
    helper used by the max-years hard rule.
  - a `CvPreferenceSuggester` port + `ClaudePreferenceSuggester` adapter
    (LLM: CV text → suggested `Preferences`). Phase 2.
- **api:** `GET /api/preferences`, `PUT /api/preferences`,
  `POST /api/preferences/suggest` (LLM autofill, Phase 2). The `run`/`results`
  routes read the stored preferences instead of the yaml.
- **frontend:** a **Preferences screen** in the flow (Upload CV → Preferences →
  Find jobs → Results), reachable anytime from the header. Components:
  `PreferencesForm`, district/role/seniority chip selectors, years slider,
  employment/company toggles, the "✨ Auto-fill from CV" button (Phase 2).

## 7. Data flow

```
Upload CV → (optional) Auto-fill from CV (LLM → suggested prefs) → review/edit
          → Save preferences (PUT /api/preferences → SQLite)
          → Find jobs (GET /api/run):
                fetch → HARD prefilter(prefs) → embed → cosine + SOFT(prefs) → sort
                (+ if LLM on: prefs injected into the ranker prompt)
          → Results
```

## 8. Error handling

- **No preferences saved yet** → the app uses the default seed (from
  `preferences.yaml`); the user is never blocked.
- **Auto-fill without an API key** → the button is disabled / returns a clear
  "add a key to use auto-fill" message; the manual form always works.
- **LLM returns malformed suggestions** → validated against the `Preferences`
  schema; on failure, the form is left for manual entry with a notice.
- **Conflicting/empty selections** (e.g. no districts + no remote) → allowed; it
  simply means "no location constraint" (nothing dropped on location).

## 9. Testing

- **Engine (offline):** each hard rule in `passes_prefilter` (district, max-years
  via `required_years`, employment, freshness, company type, title); the
  `soft_score` adjustment (role match boosts, seniority mismatch penalizes,
  ordering changes, nothing dropped); preferences round-trip in SQLite; seed-from-
  yaml on empty.
- **LLM suggester (Phase 2):** `ClaudePreferenceSuggester` with a mocked client
  returns a valid `Preferences`; malformed output handled.
- **API:** `GET/PUT /api/preferences` round-trip via TestClient; `run`/`results`
  honor stored prefs; `/api/preferences/suggest` with a mocked LLM.
- **Frontend:** the Preferences form renders all fields, submits to `PUT`, and
  the auto-fill button populates the form (mocked).

## 10. Build order (one spec, two phases)

- **Phase 1 — structured prefs + manual UI + deterministic matching (no key):**
  the full field set, SQLite storage, generalized hard prefilter + soft scoring,
  the manual Preferences screen, and the API to load/save. Entirely usable
  without an API key. This is the bulk of the value.
- **Phase 2 — LLM auto-fill from CV:** the `CvPreferenceSuggester` adapter, the
  `/api/preferences/suggest` route, and the "✨ Auto-fill from my CV" button.

## 11. Scope

**In:** structured per-user preferences (the §3 fields), manual + LLM-suggested
creation, SQLite storage, hard-filter + soft-rank matching driven by prefs, prefs
injected into the LLM ranker, the Preferences UI screen.

**Out (deferred):** user accounts / multi-user isolation; multiple saved/named
profiles; user-controlled per-field hard/soft toggles; salary/visa/language
fields; preference import/export files.

## 12. Visual design

The Preferences screen follows the existing Light-SaaS look (off-white bg, white
cards, indigo accent, rounded chips, soft shadow). Multi-selects are indigo
chips; max-years is a slider; hard fields show a small "· hard" tag, soft fields a
"★ soft" tag; an "✨ Auto-fill from my CV" button sits top-right; one "Save & Find
jobs →" primary button. Editable anytime via a "Preferences" header link.
