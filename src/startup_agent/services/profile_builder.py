import structlog

from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.ports.cv_profile_extractor import CvProfileExtractor
from startup_agent.profile.regex_extract import regex_extract

logger = structlog.get_logger(__name__)

_JUDGMENT = ("first_name", "last_name", "location", "current_title")


def build_profile(cv_text: str,
                  extractor: CvProfileExtractor | None = None) -> ApplicantProfile:
    """Regex fills contact fields; the LLM (if given) fills judgment fields.

    An LLM failure is logged and swallowed — the regex-only profile is returned.
    """
    profile = ApplicantProfile(**regex_extract(cv_text))
    if extractor is None:
        return profile
    try:
        judged = extractor.extract(cv_text)
    except Exception as exc:
        logger.warning(f"profile LLM extraction failed, using regex-only: {exc}")
        return profile
    update = {k: getattr(judged, k) for k in _JUDGMENT if getattr(judged, k)}
    return profile.model_copy(update=update)
