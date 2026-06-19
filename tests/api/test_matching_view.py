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
