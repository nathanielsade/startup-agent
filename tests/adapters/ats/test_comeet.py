import json
from pathlib import Path

from startup_agent.adapters.ats.comeet import ComeetAdapter, extract_description
from startup_agent.domain.models import AtsType, Company

FIXTURE = Path("spike/fixtures/comeet_aqua.json")


def test_comeet_builds_url_and_parses_positions():
    captured = {}
    payload = json.loads(FIXTURE.read_text())

    def fetch(url):
        captured["url"] = url
        return payload

    adapter = ComeetAdapter(fetch_json=fetch, fetch_page=lambda url: "")
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
    adapter = ComeetAdapter(fetch_json=lambda url: [], fetch_page=lambda url: "")
    assert adapter.fetch_jobs(Company(name="X", ats_type=AtsType.COMEET, ats_token=None)) == []
    assert adapter.fetch_jobs(Company(name="X", ats_type=AtsType.COMEET, ats_token="no-colon")) == []


HOSTED = Path("spike/fixtures/comeet_hosted_page.html")


def test_extract_description_from_real_hosted_page():
    desc = extract_description(HOSTED.read_text())
    assert desc is not None
    assert len(desc) > 100
    assert "Aqua" in desc          # real content from the fixture
    assert "<" not in desc         # HTML tags stripped
    assert "&nbsp;" not in desc    # entities unescaped


def test_extract_description_captures_details_sections_not_just_intro():
    # Comeet embeds the full content as a "details" array of {order,name,value};
    # the requirements (with the years) must be captured, not just the intro.
    page = (
        '<script>{"description":"Short intro blurb only.",'
        '"details":['
        '{"order":1,"name":"Description","value":"\\u003cp\\u003eBuild backend.\\u003c/p\\u003e"},'
        '{"order":2,"name":"Requirements","value":"\\u003cul\\u003e\\u003cli\\u003e5+ years experience.\\u003c/li\\u003e\\u003c/ul\\u003e"}'
        ']}</script>'
    )
    desc = extract_description(page)
    assert "5+ years experience." in desc      # requirements captured
    assert "Requirements:" in desc              # section labelled
    assert "<" not in desc                      # tags stripped


def test_extract_description_falls_back_to_intro_when_no_details():
    desc = extract_description('<script>{"description":"Just the intro."}</script>')
    assert desc == "Just the intro."


def test_extract_description_none_when_absent():
    assert extract_description("<html><body>no description here</body></html>") is None
    assert extract_description("") is None


def test_comeet_attaches_descriptions_from_hosted_pages():
    payload = [
        {"uid": "P1", "name": "Backend Engineer", "url_active_page": "https://x/1",
         "url_comeet_hosted_page": "https://www.comeet.com/jobs/acme/9/be/P1",
         "location": {"name": "Tel Aviv"}, "time_updated": "2026-01-01T00:00:00+00:00"},
        {"uid": "P2", "name": "Data Engineer", "url_active_page": "https://x/2",
         "url_comeet_hosted_page": "https://www.comeet.com/jobs/acme/9/de/P2",
         "location": {"name": "Tel Aviv"}, "time_updated": "2026-01-01T00:00:00+00:00"},
    ]
    pages = {
        "https://www.comeet.com/jobs/acme/9/be/P1":
            '<script>{"description":"Build \\u003cb\\u003ebackend\\u003c/b\\u003e services and APIs."}</script>',
        "https://www.comeet.com/jobs/acme/9/de/P2":
            '<script>{"description":"Own the data pipelines."}</script>',
    }
    adapter = ComeetAdapter(fetch_json=lambda url: payload, fetch_page=lambda url: pages[url])
    jobs = adapter.fetch_jobs(Company(name="Acme", ats_type=AtsType.COMEET, ats_token="9:tok"))
    by_title = {j.title: j for j in jobs}
    assert "backend services" in by_title["Backend Engineer"].description
    assert "<b>" not in by_title["Backend Engineer"].description   # tags stripped
    assert by_title["Data Engineer"].description == "Own the data pipelines."


def test_comeet_description_failure_is_graceful():
    payload = [
        {"uid": "P1", "name": "Backend Engineer", "url_active_page": "https://x/1",
         "url_comeet_hosted_page": "https://ok", "location": {"name": "Tel Aviv"}},
        {"uid": "P2", "name": "Data Engineer", "url_active_page": "https://x/2",
         "url_comeet_hosted_page": "https://boom", "location": {"name": "Tel Aviv"}},
    ]

    def fetch_page(url):
        if url == "https://boom":
            raise RuntimeError("network down")
        return '<script>{"description":"Good description."}</script>'

    adapter = ComeetAdapter(fetch_json=lambda url: payload, fetch_page=fetch_page)
    jobs = adapter.fetch_jobs(Company(name="Acme", ats_type=AtsType.COMEET, ats_token="9:tok"))
    by_title = {j.title: j for j in jobs}
    assert by_title["Backend Engineer"].description == "Good description."
    assert by_title["Data Engineer"].description is None   # failed page → no desc, still returned
    assert len(jobs) == 2
