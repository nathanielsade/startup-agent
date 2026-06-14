from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import AtsType, Company, Job
from startup_agent.services.health_check import CompanyHealthChecker


class _FakeAdapter:
    def __init__(self, jobs=None, error=None):
        self._jobs, self._error = jobs or [], error

    def fetch_jobs(self, company):
        if self._error:
            raise RuntimeError(self._error)
        return self._jobs


class _FakeFactory:
    def __init__(self, mapping):  # name -> _FakeAdapter or None
        self._mapping = mapping

    def for_company(self, company):
        return self._mapping.get(company.name)


def _repo_with(*companies):
    r = SQLiteJobRepository(":memory:")
    r.init_schema()
    for c in companies:
        r.upsert_company(c)
    return r


def _job():
    return Job(company_id="c", ats_job_id="1", title="Eng", url="https://x/1")


def test_health_classifies_all_four_statuses():
    repo = _repo_with(
        Company(name="OkCo", ats_type=AtsType.GREENHOUSE),
        Company(name="EmptyCo", ats_type=AtsType.ASHBY),
        Company(name="FailCo", ats_type=AtsType.LEVER),
        Company(name="UnsupCo", ats_type=AtsType.COMEET),
    )
    factory = _FakeFactory({
        "OkCo": _FakeAdapter(jobs=[_job(), _job()]),
        "EmptyCo": _FakeAdapter(jobs=[]),
        "FailCo": _FakeAdapter(error="404 boom"),
        "UnsupCo": None,
    })
    results = {r.name: r for r in CompanyHealthChecker(repo, factory).check()}
    assert results["OkCo"].status == "ok" and results["OkCo"].job_count == 2
    assert results["EmptyCo"].status == "empty"
    assert results["FailCo"].status == "failed" and "boom" in results["FailCo"].error
    assert results["UnsupCo"].status == "unsupported"
