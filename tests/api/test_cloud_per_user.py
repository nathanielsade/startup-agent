import os

import pytest

from startup_agent.config.settings import Settings

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def client():
    try:
        conn = psycopg.connect(DSN)
    except Exception:
        pytest.skip("no test Postgres reachable")
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient

    from api import deps, repos
    from api.auth import get_current_user
    from api.main import app

    # cloud mode: Postgres + (auth bypassed per-test by overriding get_current_user)
    repos._pg_jobs = None  # reset singletons so they bind to the test DSN
    repos._pg_users = None
    app.dependency_overrides[deps.get_settings] = lambda: Settings(database_url=DSN, supabase_jwt_secret="")

    # clean per-user tables
    j, u = repos._pg(DSN)
    j._conn.execute("TRUNCATE user_profiles, user_jobs, llm_usage, events")
    j._conn.commit()

    c = TestClient(app)
    yield c, app, get_current_user
    app.dependency_overrides.clear()
    repos._pg_jobs = None
    repos._pg_users = None


def test_preferences_are_isolated_per_user(client):
    c, app, get_current_user = client

    app.dependency_overrides[get_current_user] = lambda: USER_A
    assert c.put("/api/preferences", json={"max_years": 2, "districts": ["center"]}).status_code == 200

    # user B sees defaults, not A's prefs
    app.dependency_overrides[get_current_user] = lambda: USER_B
    b = c.get("/api/preferences").json()
    assert b["max_years"] is None and b["districts"] == []

    # user A still sees their own
    app.dependency_overrides[get_current_user] = lambda: USER_A
    a = c.get("/api/preferences").json()
    assert a["max_years"] == 2 and a["districts"] == ["center"]


def test_profile_is_isolated_per_user(client):
    c, app, get_current_user = client

    app.dependency_overrides[get_current_user] = lambda: USER_A
    assert c.put("/api/profile", json={"first_name": "Netanel", "email": "a@b.com"}).status_code == 200

    app.dependency_overrides[get_current_user] = lambda: USER_B
    assert c.get("/api/profile").json()["first_name"] == ""   # B: empty

    app.dependency_overrides[get_current_user] = lambda: USER_A
    assert c.get("/api/profile").json()["email"] == "a@b.com"  # A: their own


def test_job_status_tracking_is_per_user(client):
    c, app, get_current_user = client

    app.dependency_overrides[get_current_user] = lambda: USER_A
    r = c.put("/api/jobs/job-1/status", json={"status": "applied",
                                              "snapshot": {"title": "Eng", "company": "Acme"}})
    assert r.status_code == 200 and r.json()["status"] == "applied"
    tracked = c.get("/api/tracked").json()["tracked"]
    assert len(tracked) == 1 and tracked[0]["status"] == "applied"

    # invalid status rejected
    assert c.put("/api/jobs/job-1/status", json={"status": "bogus"}).status_code == 422

    # user B has no tracking
    app.dependency_overrides[get_current_user] = lambda: USER_B
    assert c.get("/api/tracked").json()["tracked"] == []
