import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?(linkedin\.com/in/[\w\-%./]+)", re.I)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?(github\.com/[\w\-]+)", re.I)


def regex_extract(cv_text: str) -> dict:
    """Pull pattern-shaped contact fields from CV text. Missing fields are omitted."""
    out: dict = {}
    if m := _EMAIL.search(cv_text):
        out["email"] = m.group(0)
    if m := _PHONE.search(cv_text):
        out["phone"] = re.sub(r"\s+", " ", m.group(0)).strip()
    if m := _LINKEDIN.search(cv_text):
        out["linkedin_url"] = "https://" + m.group(1).rstrip("/.")
    if m := _GITHUB.search(cv_text):
        out["github_url"] = "https://" + m.group(1).rstrip("/.")
    return out
