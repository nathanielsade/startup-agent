from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.user_repository import UserRepository

_SCHEMA_PATH = Path(__file__).parent / "pg_schema.sql"


def _b(value) -> bytes | None:
    return bytes(value) if value is not None else None


class PostgresUserRepository(UserRepository):
    def __init__(self, dsn: str) -> None:
        self._conn = psycopg.connect(dsn, row_factory=dict_row)

    def init_schema(self) -> None:
        self._conn.execute(_SCHEMA_PATH.read_text())
        self._conn.commit()

    def save_cv(self, user_id: str, text: str, embedding: bytes | None, model: str) -> None:
        self._conn.execute(
            """INSERT INTO user_profiles (user_id, cv_text, cv_embedding, embed_model, cv_uploaded_at)
               VALUES (%s,%s,%s,%s, now())
               ON CONFLICT (user_id) DO UPDATE SET cv_text=EXCLUDED.cv_text,
                 cv_embedding=EXCLUDED.cv_embedding, embed_model=EXCLUDED.embed_model,
                 cv_uploaded_at=now(), updated_at=now()""",
            (user_id, text, embedding, model))
        self._conn.commit()

    def get_cv(self, user_id: str) -> dict | None:
        r = self._conn.execute(
            "SELECT cv_text, cv_embedding, embed_model FROM user_profiles WHERE user_id=%s",
            (user_id,)).fetchone()
        if not r or r["cv_text"] is None:
            return None
        return {"text": r["cv_text"], "embedding": _b(r["cv_embedding"]), "model": r["embed_model"]}

    def save_preferences(self, user_id: str, preferences: Preferences) -> None:
        self._conn.execute(
            """INSERT INTO user_profiles (user_id, preferences) VALUES (%s,%s)
               ON CONFLICT (user_id) DO UPDATE SET preferences=EXCLUDED.preferences, updated_at=now()""",
            (user_id, Jsonb(preferences.model_dump())))
        self._conn.commit()

    def get_preferences(self, user_id: str) -> Preferences | None:
        r = self._conn.execute(
            "SELECT preferences FROM user_profiles WHERE user_id=%s", (user_id,)).fetchone()
        if not r or r["preferences"] is None:
            return None
        return Preferences.model_validate(r["preferences"])

    def save_applicant_profile(self, user_id: str, profile: ApplicantProfile) -> None:
        self._conn.execute(
            """INSERT INTO user_profiles (user_id, applicant_profile) VALUES (%s,%s)
               ON CONFLICT (user_id) DO UPDATE SET applicant_profile=EXCLUDED.applicant_profile, updated_at=now()""",
            (user_id, Jsonb(profile.model_dump())))
        self._conn.commit()

    def get_applicant_profile(self, user_id: str) -> ApplicantProfile | None:
        r = self._conn.execute(
            "SELECT applicant_profile FROM user_profiles WHERE user_id=%s", (user_id,)).fetchone()
        if not r or r["applicant_profile"] is None:
            return None
        return ApplicantProfile.model_validate(r["applicant_profile"])

    def get_job_state(self, user_id: str, job_id: str) -> dict | None:
        r = self._conn.execute(
            "SELECT status, job_snapshot, llm_score, llm_reason, scored_at "
            "FROM user_jobs WHERE user_id=%s AND job_id=%s", (user_id, job_id)).fetchone()
        return dict(r) if r else None

    def set_job_status(self, user_id: str, job_id: str, status: str,
                       job_snapshot: dict | None = None) -> None:
        self._conn.execute(
            """INSERT INTO user_jobs (user_id, job_id, status, job_snapshot) VALUES (%s,%s,%s,%s)
               ON CONFLICT (user_id, job_id) DO UPDATE SET status=EXCLUDED.status,
                 job_snapshot=COALESCE(EXCLUDED.job_snapshot, user_jobs.job_snapshot), updated_at=now()""",
            (user_id, job_id, status, Jsonb(job_snapshot) if job_snapshot else None))
        self._conn.commit()

    def cache_llm_score(self, user_id: str, job_id: str, score: int, reason: str) -> None:
        self._conn.execute(
            """INSERT INTO user_jobs (user_id, job_id, llm_score, llm_reason, scored_at)
               VALUES (%s,%s,%s,%s, now())
               ON CONFLICT (user_id, job_id) DO UPDATE SET llm_score=EXCLUDED.llm_score,
                 llm_reason=EXCLUDED.llm_reason, scored_at=now(), updated_at=now()""",
            (user_id, job_id, score, reason))
        self._conn.commit()

    def get_tracked_jobs(self, user_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT job_id, status, job_snapshot, llm_score, llm_reason FROM user_jobs WHERE user_id=%s",
            (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def bump_llm_usage(self, user_id: str) -> int:
        cur = self._conn.execute(
            """INSERT INTO llm_usage (user_id, day, count) VALUES (%s, CURRENT_DATE, 1)
               ON CONFLICT (user_id, day) DO UPDATE SET count = llm_usage.count + 1 RETURNING count""",
            (user_id,))
        n = cur.fetchone()["count"]
        self._conn.commit()
        return int(n)

    def get_llm_usage(self, user_id: str) -> int:
        r = self._conn.execute(
            "SELECT count FROM llm_usage WHERE user_id=%s AND day=CURRENT_DATE", (user_id,)).fetchone()
        return int(r["count"]) if r else 0

    def record_event(self, user_id: str, event_type: str, job_id: str | None = None,
                     metadata: dict | None = None) -> None:
        self._conn.execute(
            "INSERT INTO events (user_id, event_type, job_id, metadata) VALUES (%s,%s,%s,%s)",
            (user_id, event_type, job_id, Jsonb(metadata) if metadata else None))
        self._conn.commit()

    def get_events(self, user_id: str, limit: int = 500) -> list[dict]:
        rows = self._conn.execute(
            "SELECT event_type, job_id, metadata, created_at FROM events "
            "WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]
