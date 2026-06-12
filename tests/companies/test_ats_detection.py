from startup_agent.companies.ats_detection import detect_ats
from startup_agent.domain.models import AtsType


def test_detect_greenhouse_both_url_forms():
    assert detect_ats("https://boards.greenhouse.io/fireblocks") == (AtsType.GREENHOUSE, "fireblocks")
    assert detect_ats("https://job-boards.greenhouse.io/melio") == (AtsType.GREENHOUSE, "melio")


def test_detect_ashby_lever_workable_comeet():
    assert detect_ats("https://jobs.ashbyhq.com/pinecone") == (AtsType.ASHBY, "pinecone")
    assert detect_ats("https://jobs.lever.co/acme") == (AtsType.LEVER, "acme")
    assert detect_ats("https://apply.workable.com/acme/") == (AtsType.WORKABLE, "acme")
    assert detect_ats("https://acme.workable.com") == (AtsType.WORKABLE, "acme")
    assert detect_ats("https://www.comeet.com/jobs/acme/12.34") == (AtsType.COMEET, "acme")


def test_detect_unknown():
    assert detect_ats("https://www.some-startup.com/careers") == (AtsType.UNKNOWN, None)
    assert detect_ats(None) == (AtsType.UNKNOWN, None)


def test_detect_greenhouse_url_with_jobs_path():
    assert detect_ats("https://boards.greenhouse.io/fireblocks/jobs/123") == (AtsType.GREENHOUSE, "fireblocks")
