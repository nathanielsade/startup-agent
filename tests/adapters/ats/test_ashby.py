import json
from pathlib import Path

from startup_agent.adapters.ats.ashby import AshbyAdapter
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path("spike/fixtures/ashby_pinecone.json")


def test_ashby_builds_url_and_parses_jobs():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = AshbyAdapter(fetch_json=fetch)
    company = Company(name="Pinecone", ats_type=AtsType.ASHBY, ats_token="pinecone")
    jobs = adapter.fetch_jobs(company)

    assert captured["url"] == "https://api.ashbyhq.com/posting-api/job-board/pinecone"
    assert len(jobs) == 7
    j = jobs[0]
    assert j.company_id == company.id_hash
    assert j.ats_job_id == "7261adcb-026d-4552-8f89-7a46156c40c5"
    assert j.title == "Staff/Principal Product Manager, Database"
    assert j.location == "US Remote"
    assert j.url == "https://jobs.ashbyhq.com/pinecone/7261adcb-026d-4552-8f89-7a46156c40c5"
    assert "Pinecone" in (j.description or "")     # descriptionPlain
    assert j.posted_at is not None                  # publishedAt


def test_ashby_handles_empty_board():
    adapter = AshbyAdapter(fetch_json=lambda url: {"jobs": []})
    company = Company(name="Empty", ats_type=AtsType.ASHBY, ats_token="empty")
    assert adapter.fetch_jobs(company) == []
