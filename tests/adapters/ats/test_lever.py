import json
from pathlib import Path

from startup_agent.adapters.ats.lever import LeverAdapter
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path(__file__).parents[3] / "spike" / "fixtures" / "lever_biocatch.json"


def test_lever_builds_url_and_parses_list_payload():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = LeverAdapter(fetch_json=fetch)
    company = Company(name="BioCatch", ats_type=AtsType.LEVER, ats_token="biocatch")
    jobs = adapter.fetch_jobs(company)

    assert captured["url"] == "https://api.lever.co/v0/postings/biocatch?mode=json"
    assert len(jobs) == 13
    j = jobs[0]
    assert j.company_id == company.id_hash
    assert j.title
    assert j.url.startswith("https://jobs.lever.co/biocatch/")
    assert j.posted_at is not None


def test_lever_parses_ms_epoch_and_location():
    payload = [{
        "id": "abc", "text": "Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/x/abc",
        "categories": {"location": "Tel-Aviv"},
        "descriptionPlain": "build things", "createdAt": 1777313306004,
    }]
    adapter = LeverAdapter(fetch_json=lambda url: payload)
    jobs = adapter.fetch_jobs(Company(name="X", ats_type=AtsType.LEVER, ats_token="x"))
    assert jobs[0].location == "Tel-Aviv"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].posted_at.year == 2026


def test_lever_skips_malformed_job():
    payload = [{"id": "bad"}, {"id": "ok", "text": "Engineer",
               "hostedUrl": "https://jobs.lever.co/x/ok", "categories": {"location": "Tel-Aviv"}}]
    adapter = LeverAdapter(fetch_json=lambda url: payload)
    jobs = adapter.fetch_jobs(Company(name="X", ats_type=AtsType.LEVER, ats_token="x"))
    assert len(jobs) == 1
    assert jobs[0].title == "Engineer"
