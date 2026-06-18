import json
from pathlib import Path

from startup_agent.adapters.ats.comeet import ComeetAdapter
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path("spike/fixtures/comeet_aqua.json")


def test_comeet_builds_url_and_parses_positions():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = ComeetAdapter(fetch_json=fetch)
    company = Company(name="Aqua", ats_type=AtsType.COMEET, ats_token="91.001:SECRETTOKEN")
    jobs = adapter.fetch_jobs(company)

    assert captured["url"] == "https://www.comeet.co/careers-api/2.0/company/91.001/positions?token=SECRETTOKEN"
    assert len(jobs) == 12
    j = jobs[0]
    assert j.company_id == company.id_hash
    assert j.ats_job_id          # from position uid
    assert j.title               # from name
    assert j.url                 # from url_active_page
    assert "Israel" in (j.location or "")   # location.name includes country
    assert j.posted_at is not None          # from time_updated


def test_comeet_missing_token_returns_empty():
    adapter = ComeetAdapter(fetch_json=lambda url: [])
    assert adapter.fetch_jobs(Company(name="X", ats_type=AtsType.COMEET, ats_token=None)) == []
    assert adapter.fetch_jobs(Company(name="X", ats_type=AtsType.COMEET, ats_token="no-colon")) == []
