import io
from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.preferences import Preferences


def _pdf():
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


class _FakeSuggester:
    def suggest(self, cv_text):
        return Preferences(max_years=3, roles=["backend"], seniority=["junior"],
                           title_include=["engineer"])


class _RaisingSuggester:
    def suggest(self, cv_text):
        raise RuntimeError("provider exploded")


def test_suggest_merges_inferable_onto_current(client, settings):
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    # current prefs have user-chosen districts/remote we must NOT overwrite
    repo.save_preferences(Preferences(districts=["center"], include_remote=False,
                                      posted_within_days=14))
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_suggester] = lambda: _FakeSuggester()

    resp = client.post("/api/preferences/suggest")
    assert resp.status_code == 200
    body = resp.json()
    # inferable fields came from the suggester
    assert body["max_years"] == 3 and body["roles"] == ["backend"]
    assert body["seniority"] == ["junior"] and body["title_include"] == ["engineer"]
    # pure-preference fields preserved from current
    assert body["districts"] == ["center"] and body["include_remote"] is False
    assert body["posted_within_days"] == 14


def test_suggest_without_llm_returns_400(client, settings):
    app.dependency_overrides[deps.get_suggester] = lambda: None
    resp = client.post("/api/preferences/suggest")
    assert resp.status_code == 400


def test_suggest_without_cv_returns_400(client, settings):
    app.dependency_overrides[deps.get_suggester] = lambda: _FakeSuggester()
    resp = client.post("/api/preferences/suggest")  # no CV uploaded
    assert resp.status_code == 400


def test_suggest_provider_error_returns_502(client, settings):
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_suggester] = lambda: _RaisingSuggester()
    resp = client.post("/api/preferences/suggest")
    assert resp.status_code == 502
