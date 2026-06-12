import json
from pathlib import Path

from startup_agent.adapters.ats.greenhouse import GreenhouseAdapter
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path("spike/fixtures/greenhouse_fireblocks.json")


def test_greenhouse_builds_correct_url_and_parses_jobs():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = GreenhouseAdapter(fetch_json=fetch)
    company = Company(name="Fireblocks", ats_type=AtsType.GREENHOUSE, ats_token="fireblocks")
    jobs = adapter.fetch_jobs(company)

    assert captured["url"] == "https://boards-api.greenhouse.io/v1/boards/fireblocks/jobs?content=true"
    assert len(jobs) == 50
    j = jobs[0]
    assert j.company_id == company.id_hash
    assert j.ats_job_id == "4655907006"          # int id -> str
    assert j.title == "AI Secops Tech-lead"
    assert j.location == "Tel Aviv-Yafo, Tel Aviv District, Israel"
    assert j.url.startswith("https://www.fireblocks.com/careers/position/4655907006")
    assert "digital assets" in (j.description or "")   # HTML entities unescaped
    assert "&lt;" not in (j.description or "")          # entities decoded
    assert j.posted_at is not None                      # from first_published


def test_greenhouse_handles_empty_board():
    adapter = GreenhouseAdapter(fetch_json=lambda url: {"jobs": []})
    company = Company(name="Empty", ats_type=AtsType.GREENHOUSE, ats_token="empty")
    assert adapter.fetch_jobs(company) == []


def test_greenhouse_skips_malformed_job_keeps_good_ones():
    payload = {"jobs": [
        {"id": "bad"},  # missing title/absolute_url -> skipped
        {
            "id": "good",
            "title": "Engineer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/good",
            "location": {"name": "Tel Aviv"},
            "content": "desc",
            "first_published": "2026-01-01T00:00:00+00:00",
        },
    ]}
    adapter = GreenhouseAdapter(fetch_json=lambda url: payload)
    jobs = adapter.fetch_jobs(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    assert len(jobs) == 1
    assert jobs[0].title == "Engineer"
