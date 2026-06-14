from datetime import datetime, timezone

from startup_agent.domain.models import Job
from startup_agent.digest.renderer import render_markdown


def _job(ats_id: str, title: str, url: str, company_id: str = "co1") -> Job:
    return Job(company_id=company_id, ats_job_id=ats_id, title=title, url=url)


def test_render_markdown_contains_clickable_link():
    job = _job("1", "Backend Engineer", "https://example.com/jobs/1")
    entries = [(job, 85, None)]
    company_names = {"co1": "Acme"}
    md = render_markdown("2026-06-14", entries, company_names)
    assert "[Backend Engineer @ Acme](https://example.com/jobs/1)" in md


def test_render_markdown_shows_new_count_in_header():
    job = _job("1", "SRE", "https://example.com/jobs/2")
    entries = [(job, 70, None)]
    company_names = {"co1": "Acme"}
    md = render_markdown("2026-06-14", entries, company_names)
    assert "(1 new)" in md


def test_render_markdown_no_entries_shows_no_new_message():
    md = render_markdown("2026-06-14", [], {})
    assert "_No new matching jobs._" in md
    assert "(0 new)" in md


def test_render_markdown_includes_reason_when_present():
    job = _job("1", "ML Engineer", "https://example.com/jobs/3")
    entries = [(job, 90, "Strong Python match")]
    company_names = {"co1": "Acme"}
    md = render_markdown("2026-06-14", entries, company_names)
    assert "Strong Python match" in md


def test_render_markdown_omits_reason_when_none():
    job = _job("1", "DevOps", "https://example.com/jobs/4")
    entries = [(job, 60, None)]
    company_names = {"co1": "Acme"}
    md = render_markdown("2026-06-14", entries, company_names)
    # Line should not have a trailing " — None"
    assert " — None" not in md


def test_render_markdown_shows_age_for_recent_job():
    now = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
    posted = datetime(2026, 6, 12, 12, 0, 0, tzinfo=timezone.utc)
    job = Job(company_id="co1", ats_job_id="1", title="PM", url="https://x/1", posted_at=posted)
    entries = [(job, 75, None)]
    md = render_markdown("2026-06-14", entries, {"co1": "Acme"}, now=now)
    assert "2d ago" in md
