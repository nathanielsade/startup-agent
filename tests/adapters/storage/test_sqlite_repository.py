import sqlite3

import pytest

from startup_agent.domain.models import AtsType, Company, Job, MatchResult, RunReport


def test_upsert_and_get_company(repo):
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.LEVER, ats_token="acme"))
    companies = repo.get_companies()
    assert len(companies) == 1
    assert companies[0].name == "Acme"


def test_upsert_job_returns_true_only_first_time(repo):
    repo.upsert_company(Company(name="Acme"))
    company_id = repo.get_companies()[0].id_hash
    job = Job(company_id=company_id, ats_job_id="1", title="Backend", url="https://x/1")
    assert repo.upsert_job(job) is True
    assert repo.upsert_job(job) is False
    assert repo.job_exists(job.id) is True


def test_record_run_and_matches(repo):
    run_id = repo.record_run(RunReport(companies_count=3, jobs_fetched=10, jobs_new=4))
    assert isinstance(run_id, int)
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job = Job(company_id=cid, ats_job_id="1", title="Backend", url="https://x/1")
    repo.upsert_job(job)
    repo.record_matches(run_id, [MatchResult(job_id=job.id, score=88, reason="fit", stage="llm")])


def test_get_companies_round_trip_preserves_fields_and_id(repo):
    original = Company(
        name="Acme", website="acme.com", careers_url="acme.com/careers",
        ats_type=AtsType.ASHBY, ats_token="acme", sector="Cyber",
        size="11-50", source="snc", active=True,
    )
    stored_id = repo.upsert_company(original)
    fetched = repo.get_companies()[0]
    assert fetched.name == original.name
    assert fetched.website == original.website
    assert fetched.careers_url == original.careers_url
    assert fetched.ats_type == original.ats_type
    assert fetched.ats_token == original.ats_token
    assert fetched.sector == original.sector
    assert fetched.size == original.size
    assert fetched.id_hash == stored_id


def test_get_companies_active_only_filter(repo):
    repo.upsert_company(Company(name="ActiveCo", active=True))
    repo.upsert_company(Company(name="InactiveCo", active=False))
    assert len(repo.get_companies()) == 1
    assert len(repo.get_companies(active_only=False)) == 2


def test_upsert_job_for_unknown_company_violates_foreign_key(repo):
    orphan = Job(company_id="does-not-exist", ats_job_id="1", title="X", url="https://x/1")
    with pytest.raises(sqlite3.IntegrityError):
        repo.upsert_job(orphan)
