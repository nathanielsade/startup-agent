from datetime import datetime, timezone

from api.schemas import job_match_from_result, to_job_match
from startup_agent.domain.models import Job, MatchResult

NOW = datetime(2026, 6, 20, tzinfo=timezone.utc)


def _job():
    return Job(company_id="cid1", ats_job_id="1", title="Backend Engineer",
               location="Tel Aviv", url="https://x/apply", description="d")


def test_to_job_match_sets_company_linkedin_url_from_links():
    links = {"cid1": "https://www.linkedin.com/company/acme"}
    m = to_job_match(_job(), 0.5, {"cid1": "Acme"}, NOW, company_links=links)
    assert m.company_linkedin_url == "https://www.linkedin.com/company/acme"


def test_to_job_match_linkedin_none_when_absent():
    m = to_job_match(_job(), 0.5, {"cid1": "Acme"}, NOW)
    assert m.company_linkedin_url is None


def test_job_match_from_result_keeps_company_linkedin_url():
    links = {"cid1": "https://www.linkedin.com/company/acme"}
    r = MatchResult(job_id="x", score=80, reason="good", stage="llm")
    m = job_match_from_result(_job(), r, {"cid1": "Acme"}, NOW, company_links=links)
    assert m.company_linkedin_url == "https://www.linkedin.com/company/acme"
    assert m.score == 80 and m.rated is True