import json
from pathlib import Path

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import AtsType, Company
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.services.ingestion import IngestionService

GH = json.loads(Path("spike/fixtures/greenhouse_fireblocks.json").read_text())
ASHBY = json.loads(Path("spike/fixtures/ashby_pinecone.json").read_text())


def _routing_fetcher(url: str) -> dict:
    if "greenhouse" in url:
        return GH
    if "ashbyhq" in url:
        return ASHBY
    return {"jobs": []}


def _seeded_repo():
    repo = SQLiteJobRepository(":memory:")
    repo.init_schema()
    repo.upsert_company(Company(name="Fireblocks", ats_type=AtsType.GREENHOUSE, ats_token="fireblocks"))
    repo.upsert_company(Company(name="Pinecone", ats_type=AtsType.ASHBY, ats_token="pinecone"))
    repo.upsert_company(Company(name="ComeetCo", ats_type=AtsType.COMEET, ats_token="x"))  # unsupported -> skipped
    return repo


def test_ingestion_fetches_and_stores_new_jobs():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    service = IngestionService(repo=repo, factory=factory)

    report = service.run()
    assert report.companies_count == 3
    assert report.jobs_fetched == 57   # 50 greenhouse + 7 ashby
    assert report.jobs_new == 57
    assert report.status == "success"


def test_ingestion_logs_per_company_outcomes_and_summary():
    import structlog
    repo = _seeded_repo()  # 2 companies return jobs; the 3rd returns none
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    with structlog.testing.capture_logs() as logs:
        IngestionService(repo=repo, factory=factory).run()
    summary = next(log for log in logs if log["event"] == "ingest_summary")
    assert summary["ok"] == 2
    # the tally accounts for every company exactly once
    assert sum(summary[k] for k in
               ("ok", "failed", "empty", "filtered_foreign", "unsupported")) == 3
    results = [log for log in logs if log["event"] == "company_result"]
    assert len(results) == 3
    assert any(r["company"] == "Fireblocks" and r["outcome"] == "ok" and r["stored"] == 50
               for r in results)


def test_ingestion_logs_filtered_foreign_when_all_jobs_dropped():
    import structlog
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    with structlog.testing.capture_logs() as logs:
        IngestionService(repo=repo, factory=factory, job_filter=lambda j: False).run()
    summary = next(log for log in logs if log["event"] == "ingest_summary")
    # both job-returning companies had all their jobs filtered out -> filtered_foreign
    assert summary["filtered_foreign"] == 2 and summary["ok"] == 0


def test_ingestion_job_filter_skips_filtered_jobs():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    # reject everything → still counts fetched, but stores nothing
    service = IngestionService(repo=repo, factory=factory, job_filter=lambda j: False)
    report = service.run()
    assert report.jobs_fetched == 57
    assert report.jobs_new == 0
    assert repo.get_jobs() == []


def test_ingestion_is_idempotent_no_duplicate_new():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    service = IngestionService(repo=repo, factory=factory)

    service.run()
    second = service.run()
    assert second.jobs_fetched == 57
    assert second.jobs_new == 0        # all already seen -> dedup


def test_ingestion_isolates_company_failure():
    repo = _seeded_repo()

    def flaky_fetcher(url: str) -> dict:
        if "greenhouse" in url:
            raise RuntimeError("boom")
        return _routing_fetcher(url)

    factory = ATSAdapterFactory(fetch_json=flaky_fetcher)
    service = IngestionService(repo=repo, factory=factory)
    report = service.run()
    # greenhouse company failed, ashby still ingested
    assert report.jobs_new == 7
    assert report.status == "partial"


def test_ingestion_progress_callback_fires_per_company():
    repo = _seeded_repo()
    factory = ATSAdapterFactory(fetch_json=_routing_fetcher)
    events = []
    IngestionService(repo=repo, factory=factory).run(progress=events.append)
    # one event per company (3 seeded), each carrying counters
    assert len(events) == 3
    assert events[0]["total"] == 3
    assert {"done", "total", "company", "jobs_fetched", "jobs_new"} <= events[-1].keys()
    assert events[-1]["done"] == 3
