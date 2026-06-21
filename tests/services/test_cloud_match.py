import os
from datetime import datetime, timezone

import pytest

from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.domain.models import AtsType, Company, Job, MatchResult
from startup_agent.domain.preferences import Preferences

DSN = os.environ.get("STARTUP_AGENT_TEST_PG",
                     "postgresql://postgres:devpass@localhost:5433/startup_agent")
psycopg = pytest.importorskip("psycopg")

USER = "33333333-3333-3333-3333-333333333333"


class _FakeRanker:
    def __init__(self, score=88):
        self.calls = 0
        self.score = score

    def rank_one(self, cv_text, job, preferences=None, card=None, district=None):
        self.calls += 1
        return MatchResult(job_id=job.id, score=self.score, reason="great fit", stage="llm")


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
    assert out[0].ai_scored is True
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
    assert len(out) == 1 and out[0].rated is False and out[0].ai_scored is False
    assert ranker.calls == 0


def test_experience_penalty_demotes_over_level_job(env):
    from startup_agent.services.cloud_match import match_for_user
    scoped, users, job_a = env
    jobs = scoped._jobs

    # Job A is well-matched (rank card requires 2 yrs == user's 2). Job B needs 8 yrs.
    jobs.store_rank_card(job_a.id, {"required_years": 2})

    job_b = Job(company_id=job_a.company_id, ats_job_id="2", title="Backend Engineer",
                url="https://x/2", location="Tel Aviv", description="go",
                posted_at=datetime.now(timezone.utc))
    jobs.upsert_job(job_b)
    jobs.store_embedding(job_b.id, to_bytes([1.0, 0.0]), "bge")   # same cosine as job A
    jobs.store_rank_card(job_b.id, {"required_years": 8})

    users.save_applicant_profile(USER, ApplicantProfile(years_experience=2))

    ranker = _FakeRanker(score=80)   # ranker returns 80 for BOTH jobs
    out = match_for_user(scoped, users, USER, _NoEmbedder(), "data/preferences.yaml",
                         threshold=0.0, ranker=ranker, cap=10)

    by_id = {m.job_id: m for m in out}
    assert by_id[job_a.id].score == 80     # gap 0 → penalty 0
    assert by_id[job_b.id].score == 30     # gap 6 → penalty 50 → 80-50
    assert by_id[job_a.id].ai_scored is True and by_id[job_b.id].ai_scored is True
    # A (80) sorts before B (30)
    assert out.index(by_id[job_a.id]) < out.index(by_id[job_b.id])
