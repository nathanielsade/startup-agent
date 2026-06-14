# ATS Unknown Categorization — Spike Results

**Run date:** 2026-06-14  
**Script:** `/tmp/ats_spike_categorizer.py`  
**Input:** `spike/fixtures/companies_recruiting.json`

---

## Totals

| Metric | Count |
|---|---|
| Total entries in file | 909 |
| Unknown/empty/null `ats_type` (attempted) | 579 |
| Successfully categorized | 579 |

---

## Results by `unknown_reason` bucket

| Bucket | Count | % of unknown |
|---|---|---|
| `careers_no_ats` | 292 | 50.4% |
| `no_careers_link` | 183 | 31.6% |
| `unknown_ats_detected` | 33 | 5.7% |
| `dead_or_unreachable` | 30 | 5.2% |
| `bot_blocked` | 27 | 4.7% |
| `known_ats_missed` | 14 | 2.4% |
| **Total** | **579** | 100% |

---

## `looks_like_spa` breakdown

| Bucket | Total | SPA | SPA % |
|---|---|---|---|
| `no_careers_link` | 183 | 30 | 16.4% |
| `careers_no_ats` | 292 | 82 | 28.1% |
| **Combined SPA** | **475** | **112** | **23.6%** |

112 companies have a JS-heavy shell that likely hides the careers page or ATS embed from static scraping — these are candidates for headless browser recovery.

---

## `unknown_ats_detected` breakdown (unsupported ATS)

| ATS | Count |
|---|---|
| phenom | 7 |
| breezy | 5 |
| successfactors | 5 |
| jobvite | 4 |
| cornerstone | 4 |
| pinpoint | 3 |
| taleo | 2 |
| jazzhr | 1 |
| talentbrew | 1 |
| icims | 1 |
| **Total** | **33** |

---

## `known_ats_missed` — supported ATS found that the original crawler missed

| ATS | Count |
|---|---|
| workday | 5 |
| greenhouse | 4 |
| comeet | 3 |
| ashby | 1 |
| workable | 1 |
| **Total** | **14** |

These 14 entries have had `ats_type` and `ats_token` (where extractable) updated in-place in the JSON.

### Example companies recovered

| Company | Website | ATS |
|---|---|---|
| Beekeeper | https://beekeeper.io | workday |
| C2i Genomics | https://c2i-genomics.com | greenhouse |
| DTCP | https://dtcp.capital | ashby |
| Healthee | https://healthee.com | workable |
| Imagen Technologies | https://imagen.ai | greenhouse |
| NeuraLight | https://neuralight.ai | greenhouse |
| Quantum Machines | https://quantum-machines.co | comeet |
| Scopio Labs | https://scopiolabs.com | comeet |
| TriEye | https://trieye.tech | comeet |

---

## Bottom line — recoverability

### (i) Recoverable via headless browser
**112 companies** (`looks_like_spa: true`) have React/Next/Angular shells that return near-empty HTML to a static scraper. A headless browser (Playwright/Puppeteer) rendering the page would likely expose the careers links and ATS embeds that are currently invisible. This is the single largest recovery lever.

- 30 in `no_careers_link` — SPA homepage hid the careers link entirely
- 82 in `careers_no_ats` — careers page loaded but ATS widget is rendered client-side

### (ii) Recoverable by adding one ATS adapter
**33 companies** use a known unsupported ATS. Adding adapters in priority order:

| ATS | Companies unlocked |
|---|---|
| phenom | 7 |
| breezy | 5 |
| successfactors | 5 |
| jobvite | 4 |
| cornerstone | 4 |
| pinpoint | 3 |
| taleo | 2 |
| jazzhr | 1 |
| talentbrew | 1 |
| icims | 1 |

Adding adapters for `phenom` + `breezy` + `successfactors` alone would recover 17 companies (52% of this bucket).

### (iii) Genuine dead / noise
**57 companies** are hard blockers with no clear software fix:
- 30 `dead_or_unreachable` — DNS failure, timeouts, 5xx, or 404 homepages
- 27 `bot_blocked` — 403/429 even for a browser-like UA (Cloudflare, etc.)

### (iv) Static scraper limitation — careers page exists but no ATS markers
**210 companies** in `careers_no_ats` (non-SPA) have a working careers page but no detectable ATS in static HTML. These could be:
- In-house job boards with no recognizable ATS
- ATS iframes loaded async (headless browser may help some)
- Companies with no open roles (empty boards that still exist)
