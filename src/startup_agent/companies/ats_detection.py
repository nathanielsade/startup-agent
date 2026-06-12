import re

from startup_agent.domain.models import AtsType

_PATTERNS: list[tuple[AtsType, re.Pattern]] = [
    (AtsType.GREENHOUSE, re.compile(r"(?:job-)?boards\.greenhouse\.io/([^/?#]+)")),
    (AtsType.ASHBY, re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)")),
    (AtsType.LEVER, re.compile(r"jobs\.lever\.co/([^/?#]+)")),
    (AtsType.WORKABLE, re.compile(r"apply\.workable\.com/([^/?#]+)")),
    (AtsType.WORKABLE, re.compile(r"([^/.]+)\.workable\.com")),
    (AtsType.SMARTRECRUITERS, re.compile(r"careers\.smartrecruiters\.com/([^/?#]+)")),
    (AtsType.COMEET, re.compile(r"comeet\.com/jobs/([^/?#]+)")),
]


def detect_ats(url: str | None) -> tuple[AtsType, str | None]:
    if not url:
        return (AtsType.UNKNOWN, None)
    for ats_type, pattern in _PATTERNS:
        match = pattern.search(url)
        if match:
            return (ats_type, match.group(1))
    return (AtsType.UNKNOWN, None)
