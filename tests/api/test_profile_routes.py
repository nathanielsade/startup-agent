import io
from pypdf import PdfWriter

from api import deps
from api.main import app
from startup_agent.domain.applicant_profile import ApplicantProfile


def _pdf():
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


class _Extractor:
    def extract(self, cv_text):
        return ApplicantProfile(first_name="Netanel", last_name="Sade", location="Tel Aviv")


def test_profile_get_put_round_trip(client, settings):
    assert client.get("/api/profile").json()["first_name"] == ""
    resp = client.put("/api/profile", json={"first_name": "Netanel", "email": "a@b.com"})
    assert resp.status_code == 200
    assert client.get("/api/profile").json()["email"] == "a@b.com"


def test_profile_extract_no_cv_returns_400(client, settings):
    app.dependency_overrides[deps.get_profile_extractor] = lambda: None
    assert client.post("/api/profile/extract").status_code == 400


def test_profile_extract_regex_only_no_key(client, settings, monkeypatch):
    import api.routes.profile as mod
    monkeypatch.setattr(mod, "_cv_text_or_400",
                        lambda repo: "Netanel\nEmail: a@b.com\nlinkedin.com/in/netanel-sade")
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_profile_extractor] = lambda: None
    body = client.post("/api/profile/extract").json()
    assert body["email"] == "a@b.com"
    assert body["linkedin_url"] == "https://linkedin.com/in/netanel-sade"
    assert body["first_name"] == ""


def test_profile_extract_with_llm_fills_names(client, settings, monkeypatch):
    import api.routes.profile as mod
    monkeypatch.setattr(mod, "_cv_text_or_400", lambda repo: "Netanel Sade CV")
    client.post("/api/cv", files={"file": ("cv.pdf", _pdf(), "application/pdf")})
    app.dependency_overrides[deps.get_profile_extractor] = lambda: _Extractor()
    body = client.post("/api/profile/extract").json()
    assert body["first_name"] == "Netanel" and body["location"] == "Tel Aviv"
