from startup_agent.adapters.ranking.prompt import preferences_clause, job_text
from startup_agent.domain.preferences import Preferences
from startup_agent.domain.models import Job


def test_preferences_clause_summarizes_set_fields():
    p = Preferences(districts=["center"], max_years=3, roles=["backend", "ai"],
                    seniority=["junior", "mid"])
    clause = preferences_clause(p)
    assert "center" in clause.lower()
    assert "3" in clause
    assert "backend" in clause.lower()


def test_preferences_clause_empty_when_no_prefs():
    assert preferences_clause(Preferences()) == ""
    assert preferences_clause(None) == ""


def test_job_text_includes_title_and_description():
    j = Job(company_id="c", ats_job_id="1", title="Backend Engineer",
            url="https://x/1", location="Tel Aviv", description="build things")
    t = job_text(j)
    assert "Backend Engineer" in t
    assert "build things" in t


def test_job_text_uses_rank_card_and_district_when_present():
    from startup_agent.adapters.ranking.prompt import job_text
    from startup_agent.domain.models import Job
    job = Job(company_id="c", ats_job_id="1", title="Backend Eng", url="u",
              location="Tel Aviv", description="LONG DESCRIPTION " * 500)
    card = {"tech_stack": ["Go"], "role_domain": "backend", "summary": "Go backend",
            "must_haves": ["Hebrew"], "domain_industry": "fintech"}
    text = job_text(job, card=card, district="center")
    assert "Go" in text and "center" in text and "fintech" in text
    assert len(text) < 1000          # card is compact, not the 4000-char description

def test_instructions_tell_model_to_ignore_seniority_years():
    from startup_agent.adapters.ranking.prompt import INSTRUCTIONS
    low = INSTRUCTIONS.lower()
    assert "ignore" in low and ("seniority" in low or "years" in low)
