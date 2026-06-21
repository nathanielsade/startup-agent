# Job Card Redesign — Design Spec

**Date:** 2026-06-21
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

Make a job card scannable enough to triage at a glance and rich enough to decide,
without overflowing. Add: a real company **logo** (initials fallback), a **match-quality
label** (not a bare number), a **job description** (teaser → expand), and a visible
company **LinkedIn** chip. Layout follows the approved "B-tightened" direction.

## 2. The card (information hierarchy)

**Collapsed (default list view — for scanning):**
- **Logo** (left) — the company's real icon; falls back to an indigo initials box.
- **Title** + a single **match pill** on the right.
- **Meta line:** `Company · Location · age`.
- **LinkedIn chip:** "Company on LinkedIn ↗".
- **Description teaser:** one line of the description + `more ▾`.
- **Actions:** `Open application →`, `Apply ▾`.

**Expanded (after `more ▾` — for deciding):**
- Full **description** (plain text) + `less ▴`.
- **"Why it fits"** — the LLM reason, shown only when the job is AI-rated.

The **Apply ▾** kit (copy-paste profile fields) stays its own separate expander, as today.

## 3. The four additions

### 3.1 Logo
- Source: `https://unavatar.io/<domain>`, where `<domain>` is derived from the company
  website (host, minus `www.`). unavatar returns a real logo when available, else the
  site favicon.
- **Fallback:** on image error, render the existing indigo **initials box** (current
  `company-avatar` behavior). So every card always has a mark.
- Rationale: Clearbit's free logo API was sunset (verified dead); unavatar is the best
  free option. Note: this is an **external image request** per card to a third-party
  proxy (public company domains only — no user data).

### 3.2 Match label
- A single pill combining **tier + score**, e.g. `Strong · ✨80`.
- Tiers from the 0–100 score: **Strong ≥ 75**, **Good 55–74**, **Weak < 55**
  (green / amber / gray).
- `✨` prefix when the job was **AI-rated** (`rated=true`); plain score otherwise
  (embedding estimate). Replaces today's bare number + separate `score-ai` styling.

### 3.3 Description
- The job description, **HTML-stripped to plain text** server-side and capped
  (~1200 chars) to bound payload size.
- **Teaser:** first line / ~140 chars when collapsed; **full** text on expand.
- Jobs with no description simply omit the teaser/section.

### 3.4 Company LinkedIn chip
- Uses the existing `company_linkedin_url` (already on `JobMatch`). Surfaced as a
  visible chip in the card; **removed from inside the Apply panel** to avoid duplication.
- Links to the direct company page when known, else the search-link fallback (unchanged
  behavior, just relocated and always visible).

**Dropped:** company sector/size tags — the data does not exist (0/256 companies have
it, and no cheap source). Out of scope; the LinkedIn chip fills that slot.

## 4. Architecture / data flow

The card needs two fields the API doesn't send today; both are sourced where
`JobMatch` is built (`api/schemas.py: to_job_match`).

- **`JobMatch` gains:** `company_website: str | None`, `description: str | None`.
  (`company_linkedin_url`, `score`, `rated`, `reason` already exist.)
- **`to_job_match`** gains a `company_websites: dict[str, str | None] | None` param
  (parallel to the existing `company_links`), and sets
  `description = _plain_text(job.description)` (new helper: strip tags, unescape,
  collapse whitespace, truncate). `job` is already passed in, so no new source needed
  for the description.
- **A new `_plain_text(html, cap=1200)`** helper in `api/schemas.py`.
- **Call sites** that build `JobMatch` thread a `sites` dict the same way they already
  thread `links`:
  - `api/matching_view.py: compute_matches` — build `sites = {c.id_hash: c.website …}`.
  - `api/routes/run.py` — build `sites` and pass to `to_job_match` and `rescore_recent`.
  - `src/startup_agent/services/recent_rescore.py: rescore_recent` — add a
    `company_websites` param threaded into `to_job_match` / `job_match_from_result`
    (mirrors the existing `company_links` threading).
  - `job_match_from_result` — add the `company_websites` param, pass through to
    `to_job_match`.

### Frontend
- **`frontend/src/api/client.ts`** `JobMatch`: add `company_website: string | null`,
  `description: string | null`.
- **`frontend/src/components/JobCard.tsx`:** logo `<img>` (unavatar from the website
  host) with `onError` → initials box; the match-label pill (tier + `✨`); the
  description teaser/expand (`open` state); the LinkedIn chip (moved out of the apply
  panel); keep the Apply panel otherwise intact (minus its LinkedIn link).
- **`frontend/src/styles/app.css`:** styles for `.logo` / fallback, the tier pills
  (strong/good/weak), the LinkedIn chip, the teaser/expand, matching the Light-SaaS look.

## 5. Error handling

- **Logo fails** (network/no icon) → `onError` swaps in the initials box; never a broken
  image.
- **No website** → skip the `<img>`, render the initials box directly.
- **No description** → omit the teaser and the expanded description section.
- **Not AI-rated** → plain score (no `✨`), no "why it fits" line.
- **Long/HTML descriptions** → `_plain_text` strips and truncates; the card never renders
  raw HTML.

## 6. Testing

**Backend (offline):**
- `_plain_text` strips tags, unescapes entities, collapses whitespace, truncates at the
  cap.
- `to_job_match` populates `company_website` from `company_websites` and `description`
  from `job.description` (stripped); both `None`-safe.
- `job_match_from_result` threads `company_websites` and keeps `description`.

**Frontend (build + behavior):**
- `npm run build` clean with the new fields.
- Logo `onError` fallback path; tier mapping (Strong/Good/Weak); teaser↔expand toggle;
  LinkedIn chip uses `company_linkedin_url`.

## 7. Scope

**In:** the redesigned `JobCard` (logo + match label + description teaser/expand +
LinkedIn chip), the two new `JobMatch` fields + `_plain_text` + the call-site plumbing,
CSS, tests.

**Out (deferred):** company sector/size (no data); save/applied status tracking;
caching/proxying logos locally; per-user tier thresholds.
