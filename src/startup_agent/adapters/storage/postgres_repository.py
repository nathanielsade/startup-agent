from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from startup_agent.domain.models import AtsType, Company, Job, MatchResult, RunReport
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.repository import JobRepository

_SCHEMA_PATH = Path(__file__).parent / "pg_schema.sql"


def _b(value) -> bytes | None:
    return bytes(value) if value is not None else None


class PostgresJobRepository(JobRepository):
    """JobRepository backed by Postgres (Supabase in cloud, local Docker in dev).

    Drop-in for SQLiteJobRepository: same port, embeddings stored as BYTEA bytes
    (identical serialization), so in-app cosine matching is unchanged.
    """

    def __init__(self, dsn: str) -> None:
        self._conn = psycopg.connect(dsn, row_factory=dict_row)

    def init_schema(self) -> None:
        self._conn.execute(_SCHEMA_PATH.read_text())
        self._conn.commit()

    def upsert_company(self, company: Company) -> str:
        cid = company.id_hash
        self._conn.execute(
            """INSERT INTO companies
               (id,name,website,careers_url,ats_type,ats_token,sector,size,source,active,linkedin_url)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET
                 website=EXCLUDED.website, careers_url=EXCLUDED.careers_url,
                 ats_type=EXCLUDED.ats_type, ats_token=EXCLUDED.ats_token,
                 sector=EXCLUDED.sector, size=EXCLUDED.size, active=EXCLUDED.active,
                 linkedin_url=EXCLUDED.linkedin_url""",
            (cid, company.name, company.website, company.careers_url, company.ats_type.value,
             company.ats_token, company.sector, company.size, company.source,
             company.active, company.linkedin_url),
        )
        self._conn.commit()
        return cid

    def get_companies(self, active_only: bool = True) -> list[Company]:
        q = "SELECT * FROM companies" + (" WHERE active = TRUE" if active_only else "")
        rows = self._conn.execute(q).fetchall()
        return [
            Company(name=r["name"], website=r["website"], careers_url=r["careers_url"],
                    ats_type=AtsType(r["ats_type"]), ats_token=r["ats_token"],
                    sector=r["sector"], size=r["size"], source=r["source"],
                    active=bool(r["active"]), linkedin_url=r["linkedin_url"])
            for r in rows
        ]

    def upsert_job(self, job: Job) -> bool:
        new = not self.job_exists(job.id)
        self._conn.execute(
            """INSERT INTO jobs
               (id,company_id,ats_job_id,title,location,url,description,posted_at,first_seen_at,last_seen_at,active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),TRUE)
               ON CONFLICT (id) DO UPDATE SET last_seen_at=now(), active=TRUE""",
            (job.id, job.company_id, job.ats_job_id, job.title, job.location, job.url,
             job.description, job.posted_at,
             job.first_seen_at or datetime.now(timezone.utc)),
        )
        self._conn.commit()
        return new

    def job_exists(self, job_id: str) -> bool:
        return self._conn.execute("SELECT 1 FROM jobs WHERE id=%s", (job_id,)).fetchone() is not None

    def record_run(self, report: RunReport) -> int:
        cur = self._conn.execute(
            """INSERT INTO runs (companies_count,jobs_fetched,jobs_new,jobs_matched,status,error)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (report.companies_count, report.jobs_fetched, report.jobs_new,
             report.jobs_matched, report.status, report.error),
        )
        rid = cur.fetchone()["id"]
        self._conn.commit()
        return int(rid)

    def record_matches(self, run_id: int, matches: list[MatchResult]) -> None:
        with self._conn.cursor() as c:
            c.executemany(
                "INSERT INTO matches (run_id,job_id,score,reason,stage) VALUES (%s,%s,%s,%s,%s)",
                [(run_id, m.job_id, m.score, m.reason, m.stage) for m in matches],
            )
        self._conn.commit()

    def save_cv(self, path: str, text: str, embedding: bytes | None, model: str) -> None:
        self._conn.execute("DELETE FROM cv")
        self._conn.execute(
            "INSERT INTO cv (path,text,embedding,model) VALUES (%s,%s,%s,%s)",
            (path, text, embedding, model),
        )
        self._conn.commit()

    def get_cv(self) -> dict | None:
        r = self._conn.execute(
            "SELECT path,text,embedding,model FROM cv ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if r is None:
            return None
        return {"path": r["path"], "text": r["text"],
                "embedding": _b(r["embedding"]), "model": r["model"]}

    def _job_from_row(self, r) -> Job:
        return Job(company_id=r["company_id"], ats_job_id=r["ats_job_id"], title=r["title"],
                   location=r["location"], url=r["url"], description=r["description"],
                   posted_at=r["posted_at"])

    def get_jobs(self) -> list[Job]:
        rows = self._conn.execute(
            "SELECT company_id,ats_job_id,title,location,url,description,posted_at "
            "FROM jobs WHERE active = TRUE"
        ).fetchall()
        return [self._job_from_row(r) for r in rows]

    def get_job(self, job_id: str) -> Job | None:
        r = self._conn.execute(
            "SELECT company_id,ats_job_id,title,location,url,description,posted_at "
            "FROM jobs WHERE id=%s", (job_id,)
        ).fetchone()
        return self._job_from_row(r) if r else None

    def set_job_embedding(self, job_id: str, embedding: bytes) -> None:
        self._conn.execute("UPDATE jobs SET embedding=%s WHERE id=%s", (embedding, job_id))
        self._conn.commit()

    def get_job_embedding(self, job_id: str) -> bytes | None:
        r = self._conn.execute("SELECT embedding FROM jobs WHERE id=%s", (job_id,)).fetchone()
        return _b(r["embedding"]) if r else None

    def get_notified_job_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT id FROM jobs WHERE notified_at IS NOT NULL").fetchall()
        return {r["id"] for r in rows}

    def mark_notified(self, job_ids: list[str]) -> None:
        with self._conn.cursor() as c:
            c.executemany("UPDATE jobs SET notified_at=now() WHERE id=%s", [(j,) for j in job_ids])
        self._conn.commit()

    def save_preferences(self, preferences: Preferences) -> None:
        self._conn.execute("DELETE FROM preferences")
        self._conn.execute("INSERT INTO preferences (json) VALUES (%s)",
                           (preferences.model_dump_json(),))
        self._conn.commit()

    def get_preferences(self) -> Preferences | None:
        r = self._conn.execute(
            "SELECT json FROM preferences ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return Preferences.model_validate_json(r["json"]) if r else None

    # ── batch-specific (not on the JobRepository ABC) ────────────────────
    def now(self):
        """The DB clock — used as the batch run-start so retire comparisons use one clock."""
        return self._conn.execute("SELECT now() AS t").fetchone()["t"]

    def jobs_needing_embedding(self, model: str) -> list[tuple[str, str]]:
        """Active jobs with no embedding or a stale embed_model → (id, embed_text)."""
        rows = self._conn.execute(
            "SELECT id, title, description FROM jobs "
            "WHERE active = TRUE AND (embedding IS NULL OR embed_model IS DISTINCT FROM %s)",
            (model,)).fetchall()
        return [(r["id"], f"{r['title']}\n{(r['description'] or '')[:2000]}") for r in rows]

    def store_embedding(self, job_id: str, embedding: bytes, model: str) -> None:
        self._conn.execute("UPDATE jobs SET embedding=%s, embed_model=%s WHERE id=%s",
                           (embedding, model, job_id))
        self._conn.commit()

    def retire_stale(self, before) -> int:
        """Soft-retire (active=FALSE) jobs not seen since `before`; never hard-delete."""
        cur = self._conn.execute(
            "UPDATE jobs SET active=FALSE "
            "WHERE active = TRUE AND (last_seen_at IS NULL OR last_seen_at < %s)", (before,))
        n = cur.rowcount
        self._conn.commit()
        return n
