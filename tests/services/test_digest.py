from startup_agent.domain.models import Company, Job
from startup_agent.services.digest import DigestService


def _make_job(company_id: str, ats_id: str, title: str) -> Job:
    return Job(company_id=company_id, ats_job_id=ats_id,
               title=title, url=f"https://example.com/{ats_id}")


class FakeChannel:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def deliver(self, title: str, body: str) -> None:
        self.calls.append((title, body))


def _renderer(title: str, entries, company_names) -> str:
    return f"digest:{title}:{len(entries)}"


def test_digest_service_delivers_all_fresh_on_first_run(repo):
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job1 = _make_job(cid, "j1", "Backend")
    job2 = _make_job(cid, "j2", "Frontend")
    repo.upsert_job(job1)
    repo.upsert_job(job2)

    channel = FakeChannel()
    entries = [(job1, 80, None), (job2, 70, None)]
    fresh = DigestService(repo, channel, _renderer).run("2026-06-14", entries, {"co1": "Acme"})

    assert len(fresh) == 2
    assert len(channel.calls) == 1
    assert channel.calls[0][0] == "2026-06-14"


def test_digest_service_marks_delivered_jobs_notified(repo):
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job1 = _make_job(cid, "j1", "Backend")
    repo.upsert_job(job1)

    entries = [(job1, 80, None)]
    DigestService(repo, FakeChannel(), _renderer).run("2026-06-14", entries, {})

    assert repo.get_notified_job_ids() == {job1.id}


def test_digest_service_deduplicates_on_second_run(repo):
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job1 = _make_job(cid, "j1", "Backend")
    job2 = _make_job(cid, "j2", "Frontend")
    repo.upsert_job(job1)
    repo.upsert_job(job2)

    entries = [(job1, 80, None), (job2, 70, None)]
    service = DigestService(repo, FakeChannel(), _renderer)

    first = service.run("2026-06-14", entries, {})
    assert len(first) == 2

    second = service.run("2026-06-15", entries, {})
    assert len(second) == 0


def test_digest_service_skips_delivery_when_nothing_new(repo):
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job1 = _make_job(cid, "j1", "Backend")
    repo.upsert_job(job1)
    entries = [(job1, 80, None)]
    channel = FakeChannel()
    service = DigestService(repo, channel, _renderer)

    service.run("2026-06-14", entries, {})        # delivers once
    again = service.run("2026-06-15", entries, {})  # nothing new

    assert again == []
    assert len(channel.calls) == 1                 # no second (clobbering) write


def test_digest_service_sorts_by_score_descending(repo):
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    job1 = _make_job(cid, "j1", "Low score")
    job2 = _make_job(cid, "j2", "High score")
    repo.upsert_job(job1)
    repo.upsert_job(job2)

    entries = [(job1, 50, None), (job2, 90, None)]
    fresh = DigestService(repo, FakeChannel(), _renderer).run("2026-06-14", entries, {})

    assert fresh[0][0].ats_job_id == "j2"
    assert fresh[1][0].ats_job_id == "j1"
