from datetime import datetime, timedelta, timezone

from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.prefilter import passes_prefilter

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _job(title, location="Tel Aviv", description="", posted_days_ago=1):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location=location, description=description,
               posted_at=NOW - timedelta(days=posted_days_ago))


def test_title_include_and_exclude():
    p = Preferences(title_include=["engineer"], exclude=["senior"])
    assert passes_prefilter(_job("Backend Engineer"), p, now=NOW) is True
    assert passes_prefilter(_job("Senior Backend Engineer"), p, now=NOW) is False
    assert passes_prefilter(_job("Product Manager"), p, now=NOW) is False  # no include kw


def test_district_filter():
    p = Preferences(districts=["center"], title_include=["engineer"])
    assert passes_prefilter(_job("Engineer", location="Haifa"), p, now=NOW) is False
    assert passes_prefilter(_job("Engineer", location="Tel Aviv"), p, now=NOW) is True


def test_max_years_no_longer_a_hard_filter_legacy():
    # max_years is now a soft signal — prefilter passes all jobs regardless of stated years
    p = Preferences(max_years=3, title_include=["engineer"])
    assert passes_prefilter(_job("Engineer", description="requires 7+ years"), p, now=NOW) is True
    assert passes_prefilter(_job("Engineer", description="2 years experience"), p, now=NOW) is True
    assert passes_prefilter(_job("Engineer", description="no years mentioned"), p, now=NOW) is True


def test_freshness_filter():
    p = Preferences(posted_within_days=7, title_include=["engineer"])
    assert passes_prefilter(_job("Engineer", posted_days_ago=2), p, now=NOW) is True
    assert passes_prefilter(_job("Engineer", posted_days_ago=30), p, now=NOW) is False


def test_empty_prefs_keep_everything_relevant():
    p = Preferences()  # no constraints
    assert passes_prefilter(_job("Anything", location="Haifa"), p, now=NOW) is True


def test_max_years_no_longer_hard_filters():
    from startup_agent.matching.prefilter import passes_prefilter
    from startup_agent.domain.models import Job
    from startup_agent.domain.preferences import Preferences
    job = Job(company_id="c", ats_job_id="1", title="Engineer", url="u",
              location="Tel Aviv", description="requires 10 years of experience")
    assert passes_prefilter(job, Preferences(max_years=3, districts=["center"])) is True
