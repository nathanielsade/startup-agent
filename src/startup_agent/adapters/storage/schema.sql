CREATE TABLE IF NOT EXISTS companies (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    website      TEXT,
    careers_url  TEXT,
    ats_type     TEXT NOT NULL DEFAULT 'unknown',
    ats_token    TEXT,
    sector       TEXT,
    size         TEXT,
    source       TEXT NOT NULL DEFAULT 'snc',
    active       INTEGER NOT NULL DEFAULT 1,
    added_at     TEXT NOT NULL,
    last_fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    company_id    TEXT NOT NULL REFERENCES companies(id),
    ats_job_id    TEXT NOT NULL,
    title         TEXT NOT NULL,
    location      TEXT,
    url           TEXT NOT NULL,
    description   TEXT,
    posted_at     TEXT,
    first_seen_at TEXT NOT NULL,
    embedding     BLOB,
    raw_json      TEXT,
    notified_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at);

CREATE TABLE IF NOT EXISTS cv (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    path       TEXT NOT NULL,
    text       TEXT NOT NULL,
    embedding  BLOB,
    model      TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    companies_count INTEGER NOT NULL DEFAULT 0,
    jobs_fetched    INTEGER NOT NULL DEFAULT 0,
    jobs_new        INTEGER NOT NULL DEFAULT 0,
    jobs_matched    INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    error           TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    score      INTEGER NOT NULL,
    reason     TEXT,
    stage      TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_matches_run ON matches(run_id);
