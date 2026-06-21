-- Postgres schema for the cloud multi-user version (Phase 1).
-- Shared tables (companies, jobs, runs, matches) + per-user tables.

CREATE TABLE IF NOT EXISTS companies (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    website         TEXT,
    careers_url     TEXT,
    ats_type        TEXT NOT NULL DEFAULT 'unknown',
    ats_token       TEXT,
    sector          TEXT,
    size            TEXT,
    source          TEXT NOT NULL DEFAULT 'snc',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    linkedin_url    TEXT,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_fetched_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    company_id    TEXT NOT NULL REFERENCES companies(id),
    ats_job_id    TEXT NOT NULL,
    title         TEXT NOT NULL,
    location      TEXT,
    url           TEXT NOT NULL,
    description   TEXT,
    posted_at     TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    embedding     BYTEA,
    embed_model   TEXT,
    rank_card     JSONB,
    notified_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);

CREATE TABLE IF NOT EXISTS runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    companies_count INTEGER NOT NULL DEFAULT 0,
    jobs_fetched    INTEGER NOT NULL DEFAULT 0,
    jobs_new        INTEGER NOT NULL DEFAULT 0,
    jobs_matched    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    error           TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id         SERIAL PRIMARY KEY,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    score      INTEGER NOT NULL,
    reason     TEXT,
    stage      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Single-tenant cv/preferences (back-compat with the existing port; the cloud
-- per-user model below supersedes these — they stay until the API is rewired).
CREATE TABLE IF NOT EXISTS cv (
    id         SERIAL PRIMARY KEY,
    path       TEXT NOT NULL,
    text       TEXT NOT NULL,
    embedding  BYTEA,
    model      TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS preferences (
    id         SERIAL PRIMARY KEY,
    json       TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Per-user tables (keyed by Supabase auth user UUID) ──────────────────────
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id           UUID PRIMARY KEY,
    cv_text           TEXT,
    cv_embedding      BYTEA,
    embed_model       TEXT,
    cv_uploaded_at    TIMESTAMPTZ,
    preferences       JSONB,
    applicant_profile JSONB,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_jobs (
    user_id      UUID NOT NULL,
    job_id       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'new',   -- new|seen|saved|applied|dismissed
    job_snapshot JSONB,                          -- survives job retirement
    llm_score    INTEGER,
    llm_reason   TEXT,
    scored_at    TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_user_jobs_user ON user_jobs(user_id);

CREATE TABLE IF NOT EXISTS llm_usage (
    user_id UUID NOT NULL,
    day     DATE NOT NULL,
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL,
    event_type TEXT NOT NULL,
    job_id     TEXT,
    metadata   JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, created_at);

-- idempotent migrations
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS rank_card JSONB;
