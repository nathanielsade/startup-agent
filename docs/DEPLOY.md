# Deploying the cloud version

Three free services + GitHub Actions. The API container is torch-free (hosted
OpenAI embeddings), so it fits Render's free tier.

```
 Vercel (frontend)  ──HTTPS+JWT──▶  Render (FastAPI)  ──▶  Supabase Postgres
        ▲                                                        ▲
        └── Supabase Auth (login/JWT)         GitHub Actions cron (batch) ──┘
```

## 0. Prerequisites (you do these — they need accounts/credentials)

- A **Supabase** project (DB + Auth).
- A **Render** account (API host).
- A **Vercel** account (frontend host).
- An **OpenAI** API key (embeddings) and optionally an **Anthropic** key (LLM rationale).

## 1. Supabase (database + auth)

1. Create a project. Pick a region near you (e.g. Frankfurt).
2. **Connect → Session pooler → URI** → this is `DATABASE_URL` (substitute your
   saved DB password for the `[YOUR-PASSWORD]` placeholder). Session pooler is the
   IPv4-friendly, persistent-connection variant Render/Actions need.
3. **Settings → API Keys**: copy the **Publishable key** (`sb_publishable_…`) →
   `VITE_SUPABASE_ANON_KEY`. **Settings → General / project page**: the **Project URL**
   (`https://<ref>.supabase.co`) → both `SUPABASE_URL` (API) and `VITE_SUPABASE_URL`
   (frontend). Modern projects (JWT Keys = ECC/RSA) verify logins via JWKS, so the
   API needs only `SUPABASE_URL` — no JWT secret. (Disable the **Data API** at
   project creation so the public key can't read your tables directly.)
4. **Authentication → Providers → Email**: enable it. (Optionally turn off
   "Confirm email" while testing so sign-ups are instant.)

No SQL to run — the API creates its tables on first boot (`init_schema()`).

## 2. Render (API)

1. **New → Blueprint**, point it at this repo. Render reads `render.yaml`.
2. Fill the `sync: false` env vars in the dashboard:
   - `DATABASE_URL` — from step 1.2 (Session pooler URI, password substituted)
   - `SUPABASE_URL` — your project URL, e.g. `https://<ref>.supabase.co` (used to
     verify logins via the project's public keys / JWKS — no secret needed)
   - `OPENAI_API_KEY` — your OpenAI key
   - `ANTHROPIC_API_KEY` — your Anthropic key (optional; omit to disable LLM rationale)
   - `CORS_ORIGINS` — set after step 3 (your Vercel URL); redeploy once known
3. Deploy. Note the service URL, e.g. `https://startup-agent-api.onrender.com`.
   Check `https://…/api/health` returns `{"status":"ok"}`.

> Free tier sleeps after ~15 min idle; first request after sleep is slow (~30s).

## 3. Vercel (frontend)

1. **Add New → Project**, import this repo. Set **Root Directory** to `frontend`.
   Framework auto-detects as Vite (`vercel.json` pins it).
2. Environment variables:
   - `VITE_SUPABASE_URL` — Supabase Project URL
   - `VITE_SUPABASE_ANON_KEY` — anon public key
   - `VITE_API_BASE` — the Render API URL from step 2.3
3. Deploy. Copy the resulting URL and put it in Render's `CORS_ORIGINS`, then
   redeploy the Render service.

## 4. GitHub Actions (the batch)

The batch (`.github/workflows/batch.yml`) runs every 6 hours: fetch all jobs,
embed the new ones (OpenAI), retire vanished ones. Add repo secrets:

- **Settings → Secrets and variables → Actions**:
  - `DATABASE_URL` — same as Render (the direct connection is fine here)
  - `OPENAI_API_KEY` — same OpenAI key

Trigger once manually (**Actions → jobs-batch → Run workflow**) to populate the DB
before the first user signs in.

## 5. Verify end-to-end

1. Open the Vercel URL → sign up / sign in.
2. Upload a CV → set preferences → see matches (precomputed by the batch).
3. Mark a job Applied/Saved → reload → status persists (per-user).

## Costs

- Supabase / Render / Vercel / GitHub Actions: **free tiers**.
- OpenAI embeddings: ~$0.02 / 1M tokens — a full batch of ~1k jobs is well under
  one cent; negligible monthly.
- LLM rationale (Anthropic): the only meaningful variable cost, capped per user
  per day via `LLM_DAILY_CAP`.

## Switching back to local embeddings

Local dev defaults to `EMBEDDING_PROVIDER=local` (sentence-transformers, in the
dev dependency group). Jobs and CVs embedded under one provider are not
comparable with the other (different vector space); the model name is stored with
each vector, so the next batch re-embeds everything when the provider changes.
