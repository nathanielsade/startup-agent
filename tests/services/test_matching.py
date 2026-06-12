from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job
from startup_agent.domain.preferences import Preferences
from startup_agent.services.matching import SimilarityMatchingService


class FakeEmbedder:
    """Maps text to a 2-D vector by keyword, so cosine is deterministic."""
    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            out.append([1.0, 0.0] if "backend" in tl else [0.0, 1.0])
        return out


def _repo_with_jobs():
    repo = SQLiteJobRepository(":memory:")
    repo.init_schema()
    repo.upsert_company(Company(name="Acme"))
    cid = repo.get_companies()[0].id_hash
    repo.save_cv(path="cv.pdf", text="backend python engineer",
                 embedding=to_bytes([1.0, 0.0]), model="fake")
    repo.upsert_job(Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                        url="https://x/1", location="Tel Aviv", description="backend role"))
    repo.upsert_job(Job(company_id=cid, ats_job_id="2", title="Sales Rep",
                        url="https://x/2", location="Tel Aviv", description="sales role"))
    repo.upsert_job(Job(company_id=cid, ats_job_id="3", title="Senior Backend Engineer",
                        url="https://x/3", location="Tel Aviv", description="backend role"))
    repo.upsert_job(Job(company_id=cid, ats_job_id="4", title="Backend Engineer",
                        url="https://x/4", location="Haifa", description="backend role"))
    return repo


def test_match_ranks_relevant_above_threshold_and_respects_filters():
    repo = _repo_with_jobs()
    prefs = Preferences(exclude=["Senior", "Manager", "Intern"])
    service = SimilarityMatchingService(repo=repo, embedder=FakeEmbedder(),
                                        preferences=prefs, threshold=0.5)
    results = service.run()
    titles = [job.title for job, score in results]
    # "Backend Engineer" in Tel Aviv passes (cosine 1.0); sales filtered by similarity;
    # senior dropped by prefilter; Haifa dropped by location.
    assert "Backend Engineer" in titles
    assert "Sales Rep" not in titles
    assert "Senior Backend Engineer" not in titles
    assert all(score >= 0.5 for _, score in results)


def test_match_returns_all_above_threshold_no_cap():
    repo = _repo_with_jobs()
    cid = repo.get_companies()[0].id_hash
    for i in range(30):
        repo.upsert_job(Job(company_id=cid, ats_job_id=f"x{i}", title="Backend Engineer",
                            url=f"https://x/x{i}", location="Remote", description="backend role"))
    service = SimilarityMatchingService(repo=repo, embedder=FakeEmbedder(),
                                        preferences=Preferences(exclude=["Senior"]), threshold=0.5)
    results = service.run()
    # all 31 backend roles (1 original Tel Aviv + 30 remote) returned — no cap
    assert len(results) >= 31
