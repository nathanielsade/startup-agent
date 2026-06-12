import pytest

from startup_agent.domain.models import AtsType, Company, Job


def test_company_requires_name_and_defaults_active():
    c = Company(name="Acme", ats_type=AtsType.GREENHOUSE, ats_token="acme")
    assert c.name == "Acme"
    assert c.ats_type is AtsType.GREENHOUSE
    assert c.active is True


def test_company_id_hash_is_stable_and_derives_from_name():
    assert Company(name="Acme").id_hash == Company(name="Acme", website="x.com").id_hash
    assert Company(name="Acme").id_hash != Company(name="Other").id_hash


def test_job_id_is_stable_hash_of_company_and_ats_job_id():
    j1 = Job(company_id="c1", ats_job_id="42", title="Backend Engineer",
             url="https://x/42", location="Tel Aviv")
    j2 = Job(company_id="c1", ats_job_id="42", title="changed later",
             url="https://x/42", location="Tel Aviv")
    assert j1.id == j2.id  # id derives only from company_id + ats_job_id


def test_unknown_ats_type_is_supported():
    assert AtsType("unknown") is AtsType.UNKNOWN


def test_match_result_rejects_out_of_range_score():
    from pydantic import ValidationError
    from startup_agent.domain.models import MatchResult
    with pytest.raises(ValidationError):
        MatchResult(job_id="j", score=150, reason="too high", stage="llm")
    MatchResult(job_id="j", score=0, reason="ok", stage="llm")
    MatchResult(job_id="j", score=100, reason="ok", stage="llm")
