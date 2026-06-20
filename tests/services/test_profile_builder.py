from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.services.profile_builder import build_profile

CV = "Netanel Sade\nEmail: a@b.com\nlinkedin.com/in/netanel-sade\n"


class _Extractor:
    def extract(self, cv_text):
        return ApplicantProfile(first_name="Netanel", last_name="Sade", location="Tel Aviv")


class _Boom:
    def extract(self, cv_text):
        raise RuntimeError("llm down")


def test_build_profile_regex_only_when_no_extractor():
    p = build_profile(CV, extractor=None)
    assert p.email == "a@b.com"
    assert p.linkedin_url == "https://linkedin.com/in/netanel-sade"
    assert p.first_name == "" and p.location == ""  # judgment fields blank


def test_build_profile_merges_llm_judgment_fields():
    p = build_profile(CV, extractor=_Extractor())
    assert p.email == "a@b.com"               # regex contact preserved
    assert p.first_name == "Netanel" and p.location == "Tel Aviv"  # llm judgment merged


def test_build_profile_llm_failure_falls_back_to_regex():
    p = build_profile(CV, extractor=_Boom())
    assert p.email == "a@b.com" and p.first_name == ""  # no exception, regex-only
