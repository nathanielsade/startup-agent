import re

# Matches "5+ years", "5 years", "minimum 5 years", "at least 5 years",
# "3-5 years" (captures the lower bound). Looks for a number near "year(s)".
_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:\+|or more)?\s*-?\s*\d{0,2}\s*years?", re.I),
    re.compile(r"(\d{1,2})\s*yrs?", re.I),
]


def required_years(description: str | None) -> int | None:
    if not description:
        return None
    candidates: list[int] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(description):
            try:
                value = int(match.group(1))
            except (ValueError, TypeError):
                continue
            if 0 < value <= 20:  # sane bound; ignore noise like "2024 years"
                candidates.append(value)
    return min(candidates) if candidates else None


_SENIORITY_YEARS = (
    ("director", 10), ("principal", 8), ("staff", 8), ("lead", 8),
    ("senior", 6), ("sr.", 6), ("junior", 1), ("entry", 1),
    ("associate", 1), ("intern", 0),
)


def years_from_title(title: str) -> int:
    t = title.lower()
    for marker, years in _SENIORITY_YEARS:
        if marker in t:
            return years
    return 3  # no seniority marker -> assume mid-level


def inferred_required_years(title: str, description: str | None,
                            card_years: int | None = None) -> int | None:
    """Best estimate of a job's required years: explicit card value, then a number
    parsed from the description, then an inference from the title's seniority."""
    if card_years is not None:
        return card_years
    parsed = required_years(description)
    if parsed is not None:
        return parsed
    return years_from_title(title)
