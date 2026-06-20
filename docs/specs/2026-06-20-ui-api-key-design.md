# UI API-Key Input — Design Spec

**Date:** 2026-06-20
**Status:** Approved design, pre-implementation
**Repo:** `nathanielsade/startup-agent` (personal)

## 1. Goal

Let a user enable the optional LLM features (AI fit-scoring + reasons + the per-job
"Rate" button) by **pasting their own API key into the web UI** — no `.env` editing
required. With a key: LLM features on. Without: the tool still works on free
embedding matching. This is the "anyone can bring their own key" model, making the
tool shareable.

## 2. Key handling — server memory until restart

- The user pastes a key (and picks a provider) in the UI. It is sent **once** to the
  server and held **in process memory** — **never written to disk**, never returned
  by any GET, masked in the input field.
- It survives until the server restarts; then the user re-enters it. (Acceptable for
  a local single-user tool, and the safest option that still works with the
  SSE-based run, which can't carry per-request auth headers.)
- `.env` remains a valid fallback: if no key is set in the UI, the server uses
  `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` from `.env` as before. The UI input simply
  adds a no-file way to provide a key and **takes precedence** when set.

## 3. Components

### Backend
- **In-memory config store** (`api/llm_config.py`): a module-level holder with
  `set_config(provider, api_key, model)`, `get_config() -> dict | None`, and
  `clear_config()`. Single-process local server, so a module global is sufficient;
  the run route's worker thread reads the same process memory.
- **Routes** (`api/routes/llm_config.py`):
  - `PUT /api/llm-config` — body `{provider: "anthropic"|"openai", api_key: str,
    model?: str}` → stores in memory → returns `{configured: true, provider}`.
  - `GET /api/llm-config` — returns `{configured: bool, provider: str|null}`.
    **Never returns the key.**
  - `DELETE /api/llm-config` — clears the in-memory key → `{configured: false}`.
- **`get_ranker()` precedence** (`api/deps.py`): build from the in-memory store
  first (if `configured`); otherwise fall back to `.env` settings via the existing
  `build_ranker(settings)`. A shared `build_ranker_from(provider, api_key, model,
  base_url)` is used by both paths so the construction logic isn't duplicated.

### Frontend
- A **"✨ AI scoring (optional)"** panel on the **Preferences screen**: a provider
  dropdown (Anthropic / OpenAI), a password-masked key field, and a Save button.
  When a key is configured it shows **"AI scoring: on (provider)"** with a
  **Remove** link; while off it shows a one-line explanation that adding a key
  unlocks AI fit-scores + reasons.
- `api/client.ts`: `getLlmConfig()`, `setLlmConfig(provider, apiKey, model?)`,
  `clearLlmConfig()`; a small `LlmConfig` type `{configured, provider}`.
- On load, the panel calls `getLlmConfig()` to reflect current state (on/off) without
  ever receiving the key.

## 4. Data flow

```
User opens Preferences → AI-scoring panel shows on/off (GET /api/llm-config)
User pastes key + picks provider → Save → PUT /api/llm-config (stored in memory)
Run / Rate → get_ranker() reads in-memory config (else .env) → LLM features active
Remove → DELETE /api/llm-config → back to embedding-only
Server restart → memory cleared → panel shows off → re-enter to re-enable
```

## 5. Error handling

- **Invalid/empty key submitted** → `PUT` requires a non-empty `api_key` and a valid
  `provider` (`anthropic`|`openai`); otherwise `422`/`400`. (We do not validate the
  key against the provider at save time — a bad key surfaces as a normal LLM error on
  the next run/rate, where it's already handled: per-job failures keep the embedding
  score; `/api/rate` returns an error the card shows.)
- **No key anywhere (UI or .env)** → `get_ranker()` returns `None`; runs are
  embedding-only and `/api/rate` returns `400` "No LLM configured" (unchanged
  behavior).
- **GET never leaks the key** — returns only `{configured, provider}`.

## 6. Testing

- **Config store:** `set/get/clear` round-trip; `get` after `clear` is `None`.
- **Routes (TestClient):** `PUT` stores and `GET` reports `configured:true` with the
  right provider **and no key field**; `DELETE` flips it back; `PUT` with empty key →
  rejected.
- **Precedence:** `get_ranker()` builds from the in-memory store when set (returns
  the right ranker type), falls back to `.env` when not, and `None` when neither.
- **Frontend:** the panel renders, reflects `configured` state, Save calls `PUT` and
  flips to "on", Remove calls `DELETE` and flips to "off".

All backend tests run offline (no real key, no network — the store holds whatever
string is posted; ranker construction is type-checked, not called).

## 7. Scope

**In:** UI key input on the Preferences screen, in-memory server storage (until
restart), `PUT/GET/DELETE /api/llm-config`, `get_ranker` precedence (memory → .env),
masked field + on/off state + Remove.

**Out (deferred):** persisting the key to disk; per-request key passing / true
multi-user isolation; validating the key with a live provider call at save time;
encrypting the in-memory value.

## 8. Visual design

The panel matches the Light-SaaS style: a bordered card section titled "✨ AI scoring
(optional)" with a muted sub-line ("Add your own API key to unlock AI fit-scores and
reasons — optional; matching works without it"). Provider dropdown + password field +
indigo Save button. When on: a small green "AI scoring: on · {provider}" pill and a
muted "Remove" text link. Sits below the preference fields, above "Save & Find jobs".
