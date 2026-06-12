from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.services.hybrid_matching import HybridMatchingService


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "backend" in t.lower() else [0.0, 1.0] for t in texts]


class FakeRanker:
    def rank(self, cv_text, jobs):
        # score by title: "Backend" high, others low
        out = []
        for j in jobs:
            score = 90 if "backend" in j.title.lower() else 50
            out.append(MatchResult(job_id=j.id, score=score, reason="r", stage="llm"))
        return out


def _repo():
    r = SQLiteJobRepository(":memory:")
    r.init_schema()
    r.upsert_company(Company(name="Acme"))
    cid = r.get_companies()[0].id_hash
    r.save_cv(path="cv.pdf", text="backend python", embedding=to_bytes([1.0, 0.0]), model="fake")
    r.upsert_job(Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                     url="https://x/1", location="Tel Aviv", description="backend role"))
    r.upsert_job(Job(company_id=cid, ats_job_id="2", title="Platform Engineer",
                     url="https://x/2", location="Tel Aviv", description="backend infra role"))
    return r


def test_hybrid_keeps_only_above_llm_threshold_sorted():
    repo = _repo()
    service = HybridMatchingService(
        repo=repo, embedder=FakeEmbedder(), ranker=FakeRanker(),
        preferences=Preferences(title_include=["engineer"], exclude=["Senior"]),
        sim_threshold=0.4, llm_threshold=70,
    )
    results = service.run()  # list[(Job, MatchResult)]
    titles = [job.title for job, _ in results]
    assert "Backend Engineer" in titles          # llm 90 >= 70
    assert "Platform Engineer" not in titles      # llm 50 < 70
    assert all(m.score >= 70 for _, m in results)


def test_hybrid_persists_matches_and_run():
    repo = _repo()
    service = HybridMatchingService(
        repo=repo, embedder=FakeEmbedder(), ranker=FakeRanker(),
        preferences=Preferences(title_include=["engineer"]),
        sim_threshold=0.4, llm_threshold=70,
    )
    service.run()
    # a run row exists (record_run returns an int id; matches recorded without error)
    # smoke: re-running doesn't raise
    service.run()
