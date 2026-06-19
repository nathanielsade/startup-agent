import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from startup_agent.domain.models import (
    AtsType, Company, Job, MatchResult, RunReport,
)
from startup_agent.ports.repository import JobRepository

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteJobRepository(JobRepository):
    def __init__(self, db_path: str = "jobs.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA_PATH.read_text())
        self._conn.commit()
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(jobs)")}
        if "notified_at" not in cols:
            self._conn.execute("ALTER TABLE jobs ADD COLUMN notified_at TEXT")
        self._conn.commit()

    def upsert_company(self, company: Company) -> str:
        cid = company.id_hash
        self._conn.execute(
            """INSERT INTO companies
               (id,name,website,careers_url,ats_type,ats_token,sector,size,source,active,added_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 website=excluded.website, careers_url=excluded.careers_url,
                 ats_type=excluded.ats_type, ats_token=excluded.ats_token,
                 sector=excluded.sector, size=excluded.size, active=excluded.active""",
            (cid, company.name, company.website, company.careers_url,
             company.ats_type.value, company.ats_token, company.sector,
             company.size, company.source, int(company.active), _now()),
        )
        self._conn.commit()
        return cid

    def get_companies(self, active_only: bool = True) -> list[Company]:
        q = "SELECT * FROM companies"
        if active_only:
            q += " WHERE active = 1"
        rows = self._conn.execute(q).fetchall()
        return [
            Company(
                name=r["name"], website=r["website"], careers_url=r["careers_url"],
                ats_type=AtsType(r["ats_type"]), ats_token=r["ats_token"],
                sector=r["sector"], size=r["size"], source=r["source"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    def upsert_job(self, job: Job) -> bool:
        if self.job_exists(job.id):
            return False
        self._conn.execute(
            """INSERT INTO jobs
               (id,company_id,ats_job_id,title,location,url,description,posted_at,first_seen_at,raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (job.id, job.company_id, job.ats_job_id, job.title, job.location,
             job.url, job.description,
             job.posted_at.isoformat() if job.posted_at else None,
             job.first_seen_at.isoformat() if job.first_seen_at else _now(),
             None),
        )
        self._conn.commit()
        return True

    def job_exists(self, job_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def record_run(self, report: RunReport) -> int:
        cur = self._conn.execute(
            """INSERT INTO runs
               (started_at,finished_at,companies_count,jobs_fetched,jobs_new,jobs_matched,status,error)
               VALUES (?,?,?,?,?,?,?,?)""",
            (_now(), _now(), report.companies_count, report.jobs_fetched,
             report.jobs_new, report.jobs_matched, report.status, report.error),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def record_matches(self, run_id: int, matches: list[MatchResult]) -> None:
        self._conn.executemany(
            """INSERT INTO matches (run_id,job_id,score,reason,stage,created_at)
               VALUES (?,?,?,?,?,?)""",
            [(run_id, m.job_id, m.score, m.reason, m.stage, _now()) for m in matches],
        )
        self._conn.commit()

    def save_cv(self, path: str, text: str, embedding: bytes | None, model: str) -> None:
        self._conn.execute("DELETE FROM cv")  # single-CV store; replace on save
        self._conn.execute(
            "INSERT INTO cv (path, text, embedding, model, updated_at) VALUES (?,?,?,?,?)",
            (path, text, embedding, model, _now()),
        )
        self._conn.commit()

    def get_cv(self) -> dict | None:
        row = self._conn.execute(
            "SELECT path, text, embedding, model FROM cv ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {"path": row["path"], "text": row["text"],
                "embedding": row["embedding"], "model": row["model"]}

    def get_jobs(self) -> list[Job]:
        rows = self._conn.execute(
            "SELECT company_id, ats_job_id, title, location, url, description, posted_at FROM jobs"
        ).fetchall()
        jobs: list[Job] = []
        for r in rows:
            jobs.append(Job(
                company_id=r["company_id"], ats_job_id=r["ats_job_id"], title=r["title"],
                location=r["location"], url=r["url"], description=r["description"],
                posted_at=datetime.fromisoformat(r["posted_at"]) if r["posted_at"] else None,
            ))
        return jobs

    def set_job_embedding(self, job_id: str, embedding: bytes) -> None:
        self._conn.execute("UPDATE jobs SET embedding = ? WHERE id = ?", (embedding, job_id))
        self._conn.commit()

    def get_job_embedding(self, job_id: str) -> bytes | None:
        row = self._conn.execute("SELECT embedding FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row["embedding"] if row else None

    def get_notified_job_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT id FROM jobs WHERE notified_at IS NOT NULL").fetchall()
        return {r["id"] for r in rows}

    def mark_notified(self, job_ids: list[str]) -> None:
        self._conn.executemany(
            "UPDATE jobs SET notified_at = ? WHERE id = ?",
            [(_now(), jid) for jid in job_ids],
        )
        self._conn.commit()

    def save_preferences(self, preferences) -> None:
        self._conn.execute("DELETE FROM preferences")
        self._conn.execute(
            "INSERT INTO preferences (json, updated_at) VALUES (?, ?)",
            (preferences.model_dump_json(), _now()),
        )
        self._conn.commit()

    def get_preferences(self):
        from startup_agent.domain.preferences import Preferences
        row = self._conn.execute(
            "SELECT json FROM preferences ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Preferences.model_validate_json(row["json"])

    def get_job(self, job_id: str):
        row = self._conn.execute(
            "SELECT company_id, ats_job_id, title, location, url, description, posted_at "
            "FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return Job(
            company_id=row["company_id"], ats_job_id=row["ats_job_id"], title=row["title"],
            location=row["location"], url=row["url"], description=row["description"],
            posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
        )
