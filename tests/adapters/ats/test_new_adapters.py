from startup_agent.adapters.ats.bamboohr import BambooHrAdapter
from startup_agent.adapters.ats.recruitee import RecruiteeAdapter
from startup_agent.adapters.ats.smartrecruiters import SmartRecruitersAdapter
from startup_agent.domain.models import AtsType, Company


def _company(token, ats):
    return Company(name="Acme", website="https://acme.com", ats_type=ats, ats_token=token)


def test_smartrecruiters_parses_postings():
    payload = {"content": [
        {"id": "111", "name": "Backend Engineer",
         "location": {"fullLocation": "Tel Aviv, Israel", "city": "Tel Aviv"},
         "releasedDate": "2026-06-19T08:25:33.648Z"},
    ]}
    jobs = SmartRecruitersAdapter(fetch_json=lambda url: payload).fetch_jobs(
        _company("Acme", AtsType.SMARTRECRUITERS))
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "Backend Engineer" and j.location == "Tel Aviv, Israel"
    assert j.url == "https://jobs.smartrecruiters.com/Acme/111"
    assert j.posted_at is not None


def test_recruitee_parses_offers_and_skips_urlless():
    payload = {"offers": [
        {"id": 5, "title": "Data Scientist", "location": "Remote job",
         "careers_url": "https://acme.recruitee.com/o/data-scientist",
         "description": "<p>do data</p>", "updated_at": "2026-06-18T00:00:00Z"},
        {"id": 6, "title": "No URL job"},  # missing url -> skipped
    ]}
    jobs = RecruiteeAdapter(fetch_json=lambda url: payload).fetch_jobs(
        _company("acme", AtsType.RECRUITEE))
    assert len(jobs) == 1
    assert jobs[0].title == "Data Scientist"
    assert jobs[0].url == "https://acme.recruitee.com/o/data-scientist"
    assert jobs[0].description == "<p>do data</p>"


def test_bamboohr_parses_list_and_builds_url():
    payload = {"meta": {"totalCount": 2}, "result": [
        {"id": "48", "jobOpeningName": "Head of Product",
         "location": {"city": "Tel Aviv", "state": "Israel"}, "isRemote": False},
        {"id": "49", "jobOpeningName": "Remote Eng", "location": {}, "isRemote": True},
    ]}
    jobs = BambooHrAdapter(fetch_json=lambda url: payload).fetch_jobs(
        _company("acmehr", AtsType.BAMBOOHR))
    assert len(jobs) == 2
    assert jobs[0].title == "Head of Product" and jobs[0].location == "Tel Aviv, Israel"
    assert jobs[0].url == "https://acmehr.bamboohr.com/careers/48"
    assert jobs[1].location == "Remote"


def test_factory_resolves_new_adapters():
    from startup_agent.factories.ats_factory import ATSAdapterFactory
    f = ATSAdapterFactory()
    assert isinstance(f.for_company(_company("x", AtsType.BAMBOOHR)), BambooHrAdapter)
    assert isinstance(f.for_company(_company("x", AtsType.RECRUITEE)), RecruiteeAdapter)
    assert isinstance(f.for_company(_company("x", AtsType.SMARTRECRUITERS)), SmartRecruitersAdapter)
