from datetime import datetime, timedelta, timezone

from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.services.recent_rescore import rescore_recent

NOW = datetime(2026, 6, 19, 12, tzinfo=timezone.utc)


def _job(ats_id, title, posted_hours_ago):
    return Job(company_id="c1", ats_job_id=ats_id, title=title, url=f"https://x/{ats_id}",
               location="Tel Aviv", posted_at=NOW - timedelta(hours=posted_hours_ago))


class _FakeRanker:
    def rank(self, cv_text, jobs, preferences=None):
        return [MatchResult(job_id=j.id, score=90, reason="llm says fit", stage="llm") for j in jobs]


def test_only_recent_jobs_get_llm_scored_and_sorted_first():
    fresh = _job("1", "Backend Engineer", posted_hours_ago=5)    # within 24h
    old = _job("2", "Data Engineer", posted_hours_ago=100)        # outside 24h
    pairs = [(old, 0.80), (fresh, 0.50)]   # embedding had old higher
    out = rescore_recent(pairs, ranker=_FakeRanker(), cv_text="cv",
                         preferences=Preferences(), recent_hours=24,
                         company_names={"c1": "Acme"}, now=NOW)
    # fresh got LLM-rated (90) and sorts first despite lower embedding
    assert out[0].job_id == fresh.id
    assert out[0].rated is True and out[0].score == 90 and out[0].reason == "llm says fit"
    # old kept embedding score, not rated
    assert out[1].job_id == old.id
    assert out[1].rated is False and out[1].score == 80


def test_ranker_failure_keeps_embedding_score():
    class _BoomRanker:
        def rank(self, *a, **k):
            raise RuntimeError("boom")
    fresh = _job("1", "Backend Engineer", posted_hours_ago=5)
    out = rescore_recent([(fresh, 0.50)], ranker=_BoomRanker(), cv_text="cv",
                         preferences=Preferences(), recent_hours=24,
                         company_names={"c1": "Acme"}, now=NOW)
    assert out[0].rated is False and out[0].score == 50
