import io
import json

from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import Company, Job, AtsType


def _blank_pdf():
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    b = io.BytesIO(); w.write(b); return b.getvalue()


class _FakeAdapter:
    def fetch_jobs(self, company):
        cid = company.id_hash
        return [Job(company_id=cid, ats_job_id="1", title="Backend Engineer",
                    url="https://x/1", location="Tel Aviv", description="backend")]


class _FakeFactory:
    def for_company(self, company):
        return _FakeAdapter()


def _events(resp):
    for line in resp.iter_lines():
        if line and line.startswith("data: "):
            yield json.loads(line[len("data: "):])


def test_run_streams_progress_then_done(client, settings):
    # seed a company into the same tmp db the client uses
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    # upload CV
    client.post("/api/cv", files={"file": ("cv.pdf", _blank_pdf(), "application/pdf")})

    app.dependency_overrides[deps.get_factory] = lambda: _FakeFactory()
    with client.stream("GET", "/api/run") as resp:
        assert resp.status_code == 200
        stages = [ev["stage"] for ev in _events(resp)]
    assert "fetching" in stages
    assert stages[-1] == "done"


def test_run_without_cv_returns_400(client, settings):
    repo = SQLiteJobRepository(settings.db_path); repo.init_schema()
    repo.upsert_company(Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme"))
    app.dependency_overrides[deps.get_factory] = lambda: _FakeFactory()
    resp = client.get("/api/run")
    assert resp.status_code == 400
