import io

from pypdf import PdfWriter


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_cv_status_reflects_whether_a_cv_exists(client):
    assert client.get("/api/cv").json()["has_cv"] is False
    client.post("/api/cv", files={"file": ("resume.pdf", _blank_pdf_bytes(), "application/pdf")})
    body = client.get("/api/cv").json()
    assert body["has_cv"] is True
    assert body["filename"] == "resume.pdf"


def test_upload_cv_stores_and_returns_ready(client):
    files = {"file": ("cv.pdf", _blank_pdf_bytes(), "application/pdf")}
    resp = client.post("/api/cv", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert "chars" in body
