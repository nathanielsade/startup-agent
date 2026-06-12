from pypdf import PdfWriter

from startup_agent.cv.loader import read_pdf_text


def test_read_pdf_text_returns_string(tmp_path):
    # a blank page is enough to prove it parses without error and returns str
    pdf = tmp_path / "cv.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(pdf, "wb") as fh:
        writer.write(fh)
    text = read_pdf_text(str(pdf))
    assert isinstance(text, str)
