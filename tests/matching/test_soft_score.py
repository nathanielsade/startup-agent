from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.soft_score import soft_adjust


def _job(title, description=""):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location="Tel Aviv", description=description)


def test_role_match_boosts_score():
    p = Preferences(roles=["backend"])
    boosted = soft_adjust(_job("Backend Engineer", "build backend services"), p, 0.50)
    none = soft_adjust(_job("Frontend Engineer", "build UIs"), p, 0.50)
    assert boosted > 0.50
    assert none == 0.50


def test_seniority_mismatch_penalizes():
    p = Preferences(seniority=["junior", "mid"])
    ok = soft_adjust(_job("Backend Engineer", "mid-level role"), p, 0.50)
    senior = soft_adjust(_job("Backend Engineer", "senior staff principal role"), p, 0.50)
    assert senior < ok


def test_no_soft_prefs_is_noop():
    assert soft_adjust(_job("Backend Engineer"), Preferences(), 0.50) == 0.50
