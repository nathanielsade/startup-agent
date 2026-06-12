from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.prefilter import passes_prefilter

PREFS = Preferences(
    title_include=["engineer", "developer", "software", "data scientist"],
    exclude=["Senior", "Manager", "Intern", "Sales Engineer", "Account Executive", "Counsel"],
)


def _job(title, location):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1", location=location)


def test_drops_excluded_seniority_and_non_eng():
    assert passes_prefilter(_job("Senior Backend Engineer", "Tel Aviv"), PREFS) is False
    assert passes_prefilter(_job("Engineering Manager", "Tel Aviv"), PREFS) is False
    assert passes_prefilter(_job("Account Executive", "Tel Aviv"), PREFS) is False
    assert passes_prefilter(_job("Sales Engineer", "Tel Aviv"), PREFS) is False
    assert passes_prefilter(_job("Corporate Counsel", "Tel Aviv"), PREFS) is False


def test_drops_non_engineering_titles_via_positive_filter():
    assert passes_prefilter(_job("Product Designer", "Tel Aviv"), PREFS) is False
    assert passes_prefilter(_job("Payroll Accountant", "Tel Aviv"), PREFS) is False


def test_drops_excluded_location():
    assert passes_prefilter(_job("Backend Engineer", "Haifa"), PREFS) is False
    assert passes_prefilter(_job("Backend Engineer", "Jerusalem"), PREFS) is False
    assert passes_prefilter(_job("Backend Engineer", "Dublin"), PREFS) is False


def test_keeps_central_and_remote_eng_roles():
    assert passes_prefilter(_job("Backend Engineer", "Tel Aviv"), PREFS) is True
    assert passes_prefilter(_job("Software Engineer", "Remote"), PREFS) is True
    assert passes_prefilter(_job("Data Scientist", "Tel Aviv"), PREFS) is True
