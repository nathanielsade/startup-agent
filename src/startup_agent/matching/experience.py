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
