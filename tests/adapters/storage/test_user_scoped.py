import os

import pytest

from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.domain.preferences import Preferences

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def scoped():
    try:
        psycopg.connect(DSN).close()
    except Exception:
        pytest.skip("no test Postgres reachable")
    from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
    from startup_agent.adapters.storage.postgres_user_repository import PostgresUserRepository
    from startup_agent.adapters.storage.user_scoped import UserScopedRepository
    jobs = PostgresJobRepository(DSN)
    jobs.init_schema()
    jobs._conn.execute("TRUNCATE matches, runs, jobs, companies, cv, preferences, "
                       "user_profiles, user_jobs, llm_usage, events RESTART IDENTITY CASCADE")
    jobs._conn.commit()
    users = PostgresUserRepository(DSN)

    def make(uid):
        return UserScopedRepository(jobs, users, uid)
    return make


def test_shared_jobs_visible_to_all_but_cv_is_per_user(scoped):
    a = scoped(USER_A)
    b = scoped(USER_B)
    # shared: a company+job created via A is visible to B
    cid = a.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    a.upsert_job(Job(company_id=cid, ats_job_id="1", title="Eng", url="https://x/1"))
    assert len(b.get_jobs()) == 1                       # jobs are shared

    # per-user: A's CV + prefs are isolated from B
    a.save_cv("cv.pdf", "A backend", b"\x01", "bge")
    a.save_preferences(Preferences(max_years=2))
    assert a.get_cv()["text"] == "A backend"
    assert a.get_preferences().max_years == 2
    assert b.get_cv() is None and b.get_preferences() is None
