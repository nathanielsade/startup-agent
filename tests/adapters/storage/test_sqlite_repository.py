from startup_agent.domain.models import Company, Job, AtsType, RunReport, MatchResult


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
