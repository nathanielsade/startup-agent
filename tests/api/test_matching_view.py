from datetime import datetime, timezone

from startup_agent.domain.models import Job
from api.schemas import to_job_match


def test_to_job_match_shapes_fields():
    job = Job(company_id="c1", ats_job_id="1", title="Backend Engineer",
             url="https://x/1", location="Tel Aviv",
             posted_at=datetime.now(timezone.utc))
    m = to_job_match(job, 0.73, {"c1": "Acme"})
    assert m.title == "Backend Engineer"
    assert m.company == "Acme"
    assert m.location == "Tel Aviv"
    assert m.score == 73          # 0.73 -> 73
    assert m.url == "https://x/1"
    assert m.age_label.endswith("ago") or m.age_label == ""


def test_job_match_has_job_id_and_rated_defaults():
    from datetime import datetime, timezone
    from startup_agent.domain.models import Job
    from api.schemas import to_job_match
    job = Job(company_id="c1", ats_job_id="1", title="Backend Engineer",
              url="https://x/1", location="Tel Aviv", posted_at=datetime.now(timezone.utc))
    m = to_job_match(job, 0.73, {"c1": "Acme"})
    assert m.job_id == job.id
    assert m.rated is False
    assert m.reason is None


def test_job_match_from_result():
    from startup_agent.domain.models import Job, MatchResult
    from api.schemas import job_match_from_result
    job = Job(company_id="c1", ats_job_id="1", title="Backend Engineer", url="https://x/1",
              location="Tel Aviv")
    result = MatchResult(job_id=job.id, score=88, reason="great fit", stage="llm")
    m = job_match_from_result(job, result, {"c1": "Acme"})
    assert m.score == 88
    assert m.reason == "great fit"
    assert m.rated is True
    assert m.job_id == job.id
