import os

import pytest

from startup_agent.companies.batch import run_batch
from startup_agent.domain.models import AtsType, Company, Job

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")


class _FakeAdapter:
    def __init__(self, jobs):
        self._jobs = jobs

    def fetch_jobs(self, company):
        return self._jobs


class _FakeFactory:
    def __init__(self, jobs):
        self._jobs = jobs

    def for_company(self, company):
        return _FakeAdapter(self._jobs)


class _FakeEmbedder:
    def embed(self, texts):
        return [[float(len(t)), 1.0] for t in texts]


@pytest.fixture
def repo():
    try:
        psycopg.connect(DSN).close()
    except Exception:
        pytest.skip("no test Postgres reachable")
    from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
    r = PostgresJobRepository(DSN)
    r.init_schema()
    r._conn.execute("TRUNCATE matches, runs, jobs, companies RESTART IDENTITY CASCADE")
    r._conn.commit()
    return r


def test_batch_ingests_embeds_then_retires_vanished(repo):
    cid = repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    j1 = Job(company_id=cid, ats_job_id="1", title="Backend Eng", url="https://x/1", description="go", location="Tel Aviv")
    j2 = Job(company_id=cid, ats_job_id="2", title="Product Manager", url="https://x/2", description="pm", location="Tel Aviv")

    # run 1: both jobs present
    r1 = run_batch(repo, _FakeFactory([j1, j2]), _FakeEmbedder(), model="bge")
    assert r1["new"] == 2 and r1["embedded"] == 2 and r1["retired"] == 0
    assert {j.title for j in repo.get_jobs()} == {"Backend Eng", "Product Manager"}
    assert repo.get_job_embedding(j1.id) is not None

    # run 2: j2 vanished from the source
    r2 = run_batch(repo, _FakeFactory([j1]), _FakeEmbedder(), model="bge")
    assert r2["retired"] == 1            # j2 retired (soft)
    assert r2["embedded"] == 0           # j1 already embedded with this model
    assert {j.title for j in repo.get_jobs()} == {"Backend Eng"}   # only active returned


def test_batch_reembeds_on_model_change(repo):
    cid = repo.upsert_company(Company(name="Acme"))
    j1 = Job(company_id=cid, ats_job_id="1", title="Eng", url="https://x/1", description="d", location="Tel Aviv")
    run_batch(repo, _FakeFactory([j1]), _FakeEmbedder(), model="modelA")
    # a different embed model → re-embed everything
    r = run_batch(repo, _FakeFactory([j1]), _FakeEmbedder(), model="modelB")
    assert r["embedded"] == 1
