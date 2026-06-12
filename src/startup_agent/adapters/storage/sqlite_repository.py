import json
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
             _now(), json.dumps({})),
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
