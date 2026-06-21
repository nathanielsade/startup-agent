import os

import pytest

from startup_agent.domain.models import AtsType, Company, Job, MatchResult, RunReport
from startup_agent.domain.preferences import Preferences

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")

psycopg = pytest.importorskip("psycopg")


@pytest.fixture
def repo():
    try:
        conn = psycopg.connect(DSN)
    except Exception:
        pytest.skip("no test Postgres reachable (set STARTUP_AGENT_TEST_PG or run the docker pg)")
    conn.close()
    from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
    r = PostgresJobRepository(DSN)
    r.init_schema()
    # clean slate
    r._conn.execute("TRUNCATE matches, runs, jobs, companies, cv, preferences "
                    "RESTART IDENTITY CASCADE")
    r._conn.commit()
    return r


def test_company_and_job_round_trip(repo):
    repo.upsert_company(Company(name="Acme", website="https://acme.com",
                                ats_type=AtsType.GREENHOUSE, ats_token="acme",
                                linkedin_url="https://www.linkedin.com/company/acme"))
    companies = repo.get_companies()
    assert len(companies) == 1 and companies[0].linkedin_url.endswith("/acme")
    cid = companies[0].id_hash

    job = Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
              location="Tel Aviv", url="https://acme.com/jobs/1", description="build things")
    assert repo.upsert_job(job) is True       # new
    assert repo.upsert_job(job) is False      # already seen
    assert repo.job_exists(job.id)
    got = repo.get_job(job.id)
    assert got.title == "Backend Engineer"
    assert len(repo.get_jobs()) == 1


def test_embedding_bytes_round_trip(repo):
    cid = repo.upsert_company(Company(name="Acme"))
    job = Job(company_id=cid, ats_job_id="1", title="Eng", url="https://x/1")
    repo.upsert_job(job)
    repo.set_job_embedding(job.id, b"\x00\x01\x02\x03")
    assert repo.get_job_embedding(job.id) == b"\x00\x01\x02\x03"


def test_cv_and_preferences_round_trip(repo):
    repo.save_cv(path="cv.pdf", text="backend python", embedding=b"\xaa\xbb", model="bge")
    cv = repo.get_cv()
    assert cv["text"] == "backend python" and cv["embedding"] == b"\xaa\xbb"

    repo.save_preferences(Preferences(districts=["center"], max_years=3))
    prefs = repo.get_preferences()
    assert prefs.districts == ["center"] and prefs.max_years == 3


def test_runs_matches_and_notified(repo):
    cid = repo.upsert_company(Company(name="Acme"))
    job = Job(company_id=cid, ats_job_id="1", title="Eng", url="https://x/1")
    repo.upsert_job(job)
    run_id = repo.record_run(RunReport(companies_count=1, jobs_fetched=1, jobs_new=1))
    repo.record_matches(run_id, [MatchResult(job_id=job.id, score=80, reason="good", stage="llm")])
    assert repo.get_notified_job_ids() == set()
    repo.mark_notified([job.id])
    assert repo.get_notified_job_ids() == {job.id}
