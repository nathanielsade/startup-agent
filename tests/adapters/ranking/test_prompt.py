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


def test_job_text_includes_title_and_location():
    j = Job(company_id="c", ats_job_id="1", title="Backend Engineer",
            url="https://x/1", location="Tel Aviv", description="build things")
    t = job_text(j)
    assert "Backend Engineer" in t
    assert "Tel Aviv" in t
