import json

from startup_agent.companies.loader import load_companies_from_seed
from startup_agent.domain.models import AtsType


def test_loader_parses_seed(tmp_path):
    seed = tmp_path / "c.json"
    seed.write_text(json.dumps([
        {"name": "Fireblocks", "website": "fireblocks.com", "ats_type": "greenhouse", "ats_token": "fireblocks"},
        {"name": "Pinecone", "website": "pinecone.io", "ats_type": "ashby", "ats_token": "pinecone"},
    ]))
    companies = load_companies_from_seed(str(seed))
    assert len(companies) == 2
    assert companies[0].ats_type is AtsType.GREENHOUSE
    assert companies[1].ats_token == "pinecone"


def test_loader_defaults_missing_ats_to_unknown(tmp_path):
    seed = tmp_path / "c.json"
    seed.write_text(json.dumps([{"name": "Mystery", "website": "mystery.com"}]))
    companies = load_companies_from_seed(str(seed))
    assert companies[0].ats_type is AtsType.UNKNOWN
