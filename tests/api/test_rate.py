import io
from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, AtsType, MatchResult


def _pdf():
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


class _FakeRanker:
    def rank(self, cv_text, jobs, preferences=None):
        return [MatchResult(job_id=j.id, score=88, reason="strong fit", stage="llm") for j in jobs]


def _seed(settings):
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    cid = repo.get_companies()[0].id_hash
    job = Job(company_id=cid, ats_job_id="1", title="Backend Engineer", url="https://x/1",
              location="Tel Aviv", description="backend")
    repo.upsert_job(job)
    return job


def test_rate_returns_score_and_reason(client, settings):
    job = _seed(settings)
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_ranker] = lambda: _FakeRanker()
    resp = client.post("/api/rate", json={"job_id": job.id})
    assert resp.status_code == 200
    assert resp.json() == {"score": 88, "reason": "strong fit"}


def test_rate_without_ranker_returns_400(client, settings):
    job = _seed(settings)
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_ranker] = lambda: None
    resp = client.post("/api/rate", json={"job_id": job.id})
    assert resp.status_code == 400
