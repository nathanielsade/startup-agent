import io

from pypdf import PdfWriter

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, AtsType


def _blank_pdf():
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def test_results_returns_matches_shape(client, settings):
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    cid = repo.get_companies()[0].id_hash
    repo.upsert_job(Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                        url="https://x/1", location="Tel Aviv", description="backend"))
    client.post("/api/cv", files={"file": ("cv.pdf", _blank_pdf(), "application/pdf")})

    resp = client.get("/api/results")
    assert resp.status_code == 200
    body = resp.json()
    assert "matches" in body
    assert isinstance(body["matches"], list)
    if body["matches"]:
        m = body["matches"][0]
        assert {"title", "company", "location", "score", "url", "age_label"} <= m.keys()
