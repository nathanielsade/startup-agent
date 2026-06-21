# Matching & Scoring Redesign — Recall → LLM Rerank with Experience Fit

**Date:** 2026-06-21
**Status:** Draft for review

## Goal

Replace the current "raw embedding cosine = fit score" model with a **recall →
rerank** model: embeddings find the relevant candidates, and a cheap LLM produces
the calibrated 0–100 fit score weighing tech-stack, experience level, and role —
the things the embedding score is blind to today.

## Why (problems with today's scoring)

1. **The fit score is a compressed cosine.** `score = int(cosine * 100)`, and for
   `text-embedding-3-small` a CV↔job cosine tops out around 0.5–0.6. So the score
   ceiling is ~65 — **"Strong" (75+) is effectively unreachable**, and the ±0.05
   role/seniority nudges are noise.
2. **Level-blind.** Embeddings capture *kind of job* (skills/domain) but not
   *experience level*. A Senior role scores as high as a mid role for the same
   skills — which is why a junior/mid candidate sees senior roles ranked "Good".
3. **Max-experience is a hard filter.** A job stating "5 years" is dropped outright
   if it exceeds `max_years`, instead of being judged and ranked.
4. **UI tiers don't match the LLM's own scale.** The LLM prompt says 40–69 = "a
   stretch", but the UI labels 55–74 as "Good" — so a stretch shows as "Good".
5. **LLM doesn't know Israeli geography.** It penalized a Tel Aviv job as "doesn't
   match center preference" — but Tel Aviv *is* the center district.

## Design overview

```
all active jobs (Israel-only, ~460)
        │  embedding cosine vs user's stored CV vector  (cheap, per-user, ~free)
        ▼
rank by cosine  ──►  candidate set =  top 25  ∪  posted in last 24h
        │
        ▼
LLM rerank (gpt-4o-mini, per job, cached per (user,job))
   → skills/role/tech/domain fit score 0–100  + one-line reason
        │
        ▼
apply deterministic EXPERIENCE-GAP penalty  (exact bands, free, predictable)
        │
        ▼
final score → tier (Strong 70+ / Stretch 40–69 / Weak <40)
        │
        ▼
results = [LLM-scored jobs, sorted]  +  [remaining jobs, embedding-ranked, "not AI-scored"]
```

**Division of labor:** the **LLM** judges skills/tech-stack/role/domain/must-haves
(its strength). The **experience-level fit is enforced in code** with the exact
asymmetric bands below, because the user specified precise numbers and LLMs apply
numeric rubrics inconsistently. This avoids double-counting: the LLM is told to
score *skills & role fit* and **not** to dock for seniority/years — code owns level.

**Precompute once, rank cheap (per-job "rank card").** At batch time we summarize
each job *once* into a compact structured **rank card** holding exactly what ranking
needs — extraction cost is O(jobs) (shared by all users), while it saves tokens on
O(jobs × users) rank calls. Rank prompts then carry the small card, not the full
4000-char description. This is what makes **batched** rank calls practical (CV once
+ many cards per call → the real multi-× token saving). The card's structured fields
(`required_years`, `tech_stack`) also let code compute experience-gap and tech
overlap deterministically (free), shrinking the LLM's job further.

## Components

### 1. Capture the user's years of experience (prerequisite)

- Add `years_experience: int | None = None` to `ApplicantProfile`.
- The CV profile extractor (`profiling/prompt.py` + `to_profile`) also returns total
  years of professional experience (best estimate from the CV; `null` if unclear).
- Stored on `user_profiles.applicant_profile` (JSONB) — no schema migration needed.
- If `null` (couldn't extract / no CV profile), the experience penalty is **skipped**
  (neutral), never guessed.

### 2. Per-job "rank card" (batch-time, shared across users)

At batch time, after a *new* job is fetched, summarize it once (gpt-4o-mini) into a
compact structured card and store it on the job (new `rank_card` JSONB column, or
reuse a metadata column):

```json
{
  "tech_stack": ["Go", "Kubernetes", "PostgreSQL"],
  "required_years": 5,
  "seniority": "senior",
  "role_domain": "backend",
  "must_haves": ["fluent Hebrew"],
  "domain_industry": "fintech",
  "summary": "Senior backend role building payment infra; Go + k8s heavy."
}
```

- Generated **only for jobs missing a current card** (incremental, like embeddings).
- `required_years` here supersedes the regex below when present (the LLM reads
  ranges/phrasing the regex misses).
- Used by the rank step *instead of* the full description → far fewer tokens, and
  makes batched rank calls practical.

### 2b. Required-years fallback (when the card lacks it)

`inferred_required_years(job) -> int | None`:
1. `rank_card.required_years` if present.
2. else `required_years(job.description)` (existing regex).
3. else infer from title seniority markers:
   `junior/entry/associate → 1`, `mid → 3`, (no marker → `3`), `senior → 6`,
   `staff/principal/lead → 8`, `director → 10`.
4. else `None` → penalty skipped.

### 3. Candidate selection

Given embedding-ranked jobs and `now`:
`candidates = top_25_by_cosine ∪ { j : j.posted_at within 24h }`.
Everything else is returned unscored (embedding order), flagged `ai_scored=false`.

### 4. LLM rerank — gpt-4o-mini, new criteria

- New setting `llm_rerank_model: str = "gpt-4o-mini"` used by the ranker in the
  cloud match path. (Extractor/suggester keep `openai_model`.)
- The prompt carries the job's **rank card** (component 2), not the full
  description — fewer tokens, and it enables batching CV-once + many cards per call.
- Revised prompt instructs the model to score **skills & role fit only** and
  **ignore experience level / seniority** (handled in code). Weighted criteria:
  | Criterion | Weight |
  |---|---|
  | Tech-stack overlap (candidate's languages/frameworks ↔ job's) | high |
  | Role / domain alignment | high |
  | Must-have requirements met (required language Hebrew/English, cert, clearance) | med-high |
  | Domain/industry match | med |
  | Skill recency (uses the core tech now vs long ago) | med |
  | Red flags (contract-not-fulltime, on-site mismatch) | surface in reason, don't gate |
- Scale calibration kept explicit: **70+ strong, 40–69 stretch, <40 poor.**
- **Geography fix:** pass the job's classified district (from `classify_location`)
  into the prompt as a fact (e.g., "Location district: center"), and tell the model
  Israeli location is already validated — do not penalize location.

### 5. Experience-gap penalty (deterministic, applied to the LLM score)

`gap = inferred_required_years − user_years` (skip if either is `None`).

| Direction | Gap (years) | Penalty (points) |
|---|---|---|
| **Underqualified** (job needs more) | 0–1 | 0 |
| | 2–3 | −15 |
| | 4–5 | −30 |
| | 6+ | −50 |
| **Overqualified** (job needs less) | 0–2 | 0 |
| | 3–5 | −5 |
| | 6+ | −12 |

`final_score = clamp(llm_skill_score − experience_penalty, 0, 100)`.
The displayed reason appends a short experience note when penalized
(e.g., "· needs ~3 more yrs than your experience").

### 6. Tier mapping (UI)

Realign `matchTier` to the scoring scale:
`Strong ≥ 70`, `Stretch 40–69` (label "Stretch", amber), `Weak < 40`.

### 7. Drop the max-experience hard filter

Remove the `max_years` check from `passes_prefilter`. `max_years` stays as a
preference but now feeds the *graded* experience signal, not a hard drop.
(Districts, freshness, title exclude/include remain hard filters.)

### 8. Cost & caching (per-user economics)

- Scores cached per `(user_id, job_id)` (existing `cache_llm_score`) — pay once;
  re-searches reuse. Only new/fresh jobs cost on subsequent searches.
- `llm_daily_cap` raised **30 → 60** (counts only *uncached* scorings).
- With gpt-4o-mini: a user's first full search ≈ **1–2¢**, then fractions of a
  cent/day. ~17× cheaper than gpt-4o. Embedding recall is effectively free.
- **Rank cards** cut each rank prompt's job portion ~5× (≈1000 → ≈150 tokens), are
  built once per job (shared), and enable batched rank calls (CV once + many cards).
- Follow-up (this spec ships single-job rank calls with cards; batching N cards per
  call is a fast follow that needs the cards to exist first).

## Data flow

**Batch (scheduler), per new job:** fetch → embed → **build rank card** (gpt-4o-mini),
all incremental (only jobs missing each artifact). Shared across all users.

**Cloud match (`match_for_user`), per search:**
1. Load user CV vector + preferences + `applicant_profile.years_experience`.
2. Prefilter (districts, freshness, title) — **no** max-years drop.
3. Cosine-rank survivors against the CV vector.
4. Build candidate set (top 25 ∪ last-24h).
5. For each candidate: cached score if present; else LLM-score from its **rank card**
   (gpt-4o-mini) until the daily cap; store cache + bump usage.
6. Apply experience-gap penalty (code) → final score → tier.
7. Sort scored; append unscored (embedding order, `ai_scored=false`).

## Files touched (estimate)

- `domain/applicant_profile.py` — add `years_experience`.
- `adapters/profiling/prompt.py` — extractor returns years.
- `adapters/summarizing/` (new) — job rank-card extractor (gpt-4o-mini) + prompt.
- `pg_schema.sql` + `postgres_repository.py` — `rank_card` JSONB column, getter/setter,
  `jobs_needing_rank_card()`.
- `companies/batch.py` — rank-card step (incremental, after embedding).
- `matching/experience.py` — add `inferred_required_years` + seniority map.
- `matching/experience_fit.py` (new) — `experience_penalty(user_years, required_years)`.
- `adapters/ranking/prompt.py` — new criteria, ignore-level instruction, district fact.
- `adapters/ranking/openai_ranker.py` — model param already supported.
- `services/cloud_match.py` — candidate selection, rerank, penalty, tiers.
- `config/settings.py` — `llm_rerank_model`, `llm_daily_cap` default 60.
- `api/schemas.py` — `ai_scored` flag; stop using cosine×100 as the headline.
- `frontend` — `matchTier` thresholds + "Stretch" label + `ai_scored` styling.

## Testing

- `experience_penalty`: table-driven across all bands, both directions, None inputs.
- `inferred_required_years`: stated number wins; title fallbacks; None.
- Candidate selection: top-25 ∪ last-24h union, dedup, ordering.
- `match_for_user`: experience penalty demotes an over-level job below an on-level
  one with equal skill score; unscored tail flagged; cap honored; cache reused.
- Prefilter: max-years no longer drops; districts/freshness/title still do.
- Profile extractor: returns years (mock LLM).
- Rank card: batch builds a card per new job (mock LLM), incremental (skips jobs that
  already have one); rank uses the card text, not the full description.

## Out of scope (follow-ups)

- Aligning the **local** `/api/run` path to the same scoring (this spec targets the
  cloud `match_for_user` product path).
- Batching LLM calls.
- Auto-apply.
- Salary / company-stage criteria (not enough structured data yet).

## Resolved decisions

1. **Experience in code** — exact asymmetric bands applied deterministically; LLM
   judges skills/role only. ✅
2. **Unscored tail shown below** the AI-scored jobs with a rough embedding-derived
   score, flagged `ai_scored=false` (not hidden). ✅
3. **Keep `max_years`** in the preferences UI. Its role changes from hard filter to a
   **soft preference cap**: if set and `inferred_required_years > max_years`, apply a
   small flat penalty (**−10**) — the user's explicit "nothing more senior than this".
   This is separate from, and stacks with, the CV-based experience-gap penalty (both
   reflect over-level, which is the intended demotion). ✅
