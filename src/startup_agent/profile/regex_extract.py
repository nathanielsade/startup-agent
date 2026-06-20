import re

_EMAIL = re.compile(r"[\w.+-]+\s*@\s*[\w-]+\.[\w.-]+")  # tolerate PDF spaces around @
_PHONE_CANDIDATE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?(linkedin\.com/in/[\w\-%./]+)", re.I)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?(github\.com/[\w\-]+)", re.I)


def _extract_phone(cv_text: str) -> str | None:
    """First phone-shaped token that is a real number, not a year range.

    A real phone either starts with '+' (international) or has >= 10 digits;
    date ranges like '2019 - 2023' (8 digits, no '+') are skipped.
    """
    for m in _PHONE_CANDIDATE.finditer(cv_text):
        token = m.group(0)
        digits = re.sub(r"\D", "", token)
        if token.lstrip().startswith("+") or len(digits) >= 10:
            return re.sub(r"\s+", " ", token).strip()
    return None


def regex_extract(cv_text: str) -> dict:
    """Pull pattern-shaped contact fields from CV text. Missing fields are omitted."""
    out: dict = {}
    if m := _EMAIL.search(cv_text):
        out["email"] = re.sub(r"\s+", "", m.group(0)).rstrip(".")
    if phone := _extract_phone(cv_text):
        out["phone"] = phone
    if m := _LINKEDIN.search(cv_text):
        out["linkedin_url"] = "https://" + m.group(1).rstrip("/.")
    if m := _GITHUB.search(cv_text):
        out["github_url"] = "https://" + m.group(1).rstrip("/.")
    return out
