from startup_agent.domain.models import CompanyHealth
from startup_agent.services.health_report import render_health_report

_RESULTS = [
    CompanyHealth(name="OkCo", ats_type="greenhouse", status="ok", job_count=3, israeli_count=3),
    CompanyHealth(name="GlobalCo", ats_type="lever", status="filtered_foreign",
                  job_count=5, israeli_count=0),
    CompanyHealth(name="DeadCo", ats_type="comeet", status="failed", error="404 Not Found"),
]


def test_render_includes_summary_tally_and_sections():
    md = render_health_report(_RESULTS, "2026-06-22T00:00Z")
    assert "# Integration Status" in md
    assert "2026-06-22T00:00Z" in md
    # summary counts each status
    assert "| ok | 1 |" in md and "| filtered_foreign | 1 |" in md and "| failed | 1 |" in md
    # broken-feeds section surfaces the error to fix
    assert "DeadCo" in md and "404 Not Found" in md
    # foreign-only section flags the company to prune
    assert "GlobalCo" in md
    # full per-company table row with both counts
    assert "| OkCo | greenhouse | ok | 3 | 3 |" in md


def test_render_handles_empty_results():
    md = render_health_report([], "2026-06-22T00:00Z")
    assert "# Integration Status" in md and "0 companies" in md
