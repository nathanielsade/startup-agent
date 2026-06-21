import os
from datetime import datetime, timezone

import pytest

from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.domain.models import AtsType, Company, Job, MatchResult
from startup_agent.domain.preferences import Preferences

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")

USER = "33333333-3333-3333-3333-333333333333"


class _FakeRanker:
    def __init__(self):
        self.calls = 0

    def rank(self, cv_text, jobs, prefs=None):
        self.calls += 1
        return [MatchResult(job_id=jobs[0].id, score=88, reason="great fit", stage="llm")]


class _NoEmbedder:
    def embed(self, texts):
        raise AssertionError("should not embed — jobs are precomputed")


@pytest.fixture
def env():
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
    scoped = UserScopedRepository(jobs, users, USER)

    cid = jobs.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    job = Job(company_id=cid, ats_job_id="1", title="Backend Engineer", url="https://x/1",
              location="Tel Aviv", description="go",
              posted_at=datetime.now(timezone.utc))                     # recent → LLM-eligible
    jobs.upsert_job(job)
    jobs.store_embedding(job.id, to_bytes([1.0, 0.0]), "bge")           # precomputed vector
    users.save_cv(USER, "backend python", to_bytes([1.0, 0.0]), "bge")  # CV vector (cosine=1)
    users.save_preferences(USER, Preferences(districts=["center"]))     # Tel Aviv passes
    return scoped, users, job


def test_capped_llm_rerank_caches_and_counts(env):
    from startup_agent.services.cloud_match import match_for_user
    scoped, users, job = env
    ranker = _FakeRanker()

    out = match_for_user(scoped, users, USER, _NoEmbedder(), "data/preferences.yaml",
                         threshold=0.0, ranker=ranker, cap=5)
    assert len(out) == 1 and out[0].score == 88 and out[0].rated is True
    assert ranker.calls == 1
    assert users.get_llm_usage(USER) == 1                  # usage counted
    assert users.get_job_state(USER, job.id)["llm_score"] == 88   # cached
    assert any(e["event_type"] == "search_run" for e in users.get_events(USER))

    # second run: cached score reused, ranker NOT called again
    out2 = match_for_user(scoped, users, USER, _NoEmbedder(), "data/preferences.yaml",
                          threshold=0.0, ranker=ranker, cap=5)
    assert out2[0].score == 88 and ranker.calls == 1       # no new LLM call
    assert users.get_llm_usage(USER) == 1


def test_cap_blocks_further_llm(env):
    from startup_agent.services.cloud_match import match_for_user
    scoped, users, job = env
    ranker = _FakeRanker()
    # cap=0 → no LLM; falls back to embedding score (not rated)
    out = match_for_user(scoped, users, USER, _NoEmbedder(), "data/preferences.yaml",
                         threshold=0.0, ranker=ranker, cap=0)
    assert len(out) == 1 and out[0].rated is False and ranker.calls == 0
