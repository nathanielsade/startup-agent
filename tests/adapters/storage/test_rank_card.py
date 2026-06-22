import os
import pytest

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")
from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
from startup_agent.domain.models import AtsType, Company, Job


@pytest.fixture
def repo():
    try:
        psycopg.connect(DSN).close()
    except Exception:
        pytest.skip("no test Postgres reachable")
    r = PostgresJobRepository(DSN)
    r.init_schema()
    r._conn.execute("TRUNCATE matches, runs, jobs, companies RESTART IDENTITY CASCADE")
    return r


def test_store_and_read_rank_card(repo):
    cid = repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="a"))
    j = Job(company_id=cid, ats_job_id="1", title="Backend Eng", url="u",
            description="Go and k8s", location="Tel Aviv")
    repo.upsert_job(j)
    assert [jid for jid, _, _ in repo.jobs_needing_rank_card()] == [j.id]
    card = {"tech_stack": ["Go"], "required_years": 5, "seniority": "senior"}
    repo.store_rank_card(j.id, card)
    assert repo.get_rank_card(j.id) == card
    assert repo.jobs_needing_rank_card() == []
