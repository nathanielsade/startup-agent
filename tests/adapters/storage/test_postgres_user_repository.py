import os

import pytest

from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.domain.preferences import Preferences

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def repo():
    try:
        psycopg.connect(DSN).close()
    except Exception:
        pytest.skip("no test Postgres reachable")
    from startup_agent.adapters.storage.postgres_user_repository import PostgresUserRepository
    r = PostgresUserRepository(DSN)
    r.init_schema()
    r._conn.execute("TRUNCATE user_profiles, user_jobs, llm_usage, events")
    r._conn.commit()
    return r


def test_cv_prefs_profile_per_user(repo):
    repo.save_cv(USER_A, "backend python", b"\x01\x02", "bge")
    repo.save_preferences(USER_A, Preferences(districts=["center"], max_years=3))
    repo.save_applicant_profile(USER_A, ApplicantProfile(first_name="Netanel", email="a@b.com"))

    assert repo.get_cv(USER_A)["embedding"] == b"\x01\x02"
    assert repo.get_preferences(USER_A).max_years == 3
    assert repo.get_applicant_profile(USER_A).first_name == "Netanel"
    # isolation: USER_B sees nothing
    assert repo.get_cv(USER_B) is None and repo.get_preferences(USER_B) is None


def test_job_tracking_and_llm_cache(repo):
    repo.set_job_status(USER_A, "job1", "applied", {"title": "Eng", "company": "Acme"})
    repo.cache_llm_score(USER_A, "job1", 80, "good fit")
    st = repo.get_job_state(USER_A, "job1")
    assert st["status"] == "applied" and st["llm_score"] == 80
    assert st["job_snapshot"]["company"] == "Acme"   # snapshot survives job deletion
    tracked = repo.get_tracked_jobs(USER_A)
    assert len(tracked) == 1 and tracked[0]["job_id"] == "job1"
    assert repo.get_tracked_jobs(USER_B) == []


def test_llm_usage_counter(repo):
    assert repo.get_llm_usage(USER_A) == 0
    assert repo.bump_llm_usage(USER_A) == 1
    assert repo.bump_llm_usage(USER_A) == 2
    assert repo.get_llm_usage(USER_A) == 2
    assert repo.get_llm_usage(USER_B) == 0


def test_events_log(repo):
    repo.record_event(USER_A, "search_run", metadata={"matched": 12})
    repo.record_event(USER_A, "marked_applied", job_id="job1")
    evs = repo.get_events(USER_A)
    assert len(evs) == 2
    assert {e["event_type"] for e in evs} == {"search_run", "marked_applied"}
    assert repo.get_events(USER_B) == []
