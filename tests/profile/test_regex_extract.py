from startup_agent.profile.regex_extract import regex_extract

CV = """
Netanel Sade
Backend Engineer
Email: netanelsbt@gmail.com  |  Phone: +972 54-123-4567
linkedin.com/in/netanel-sade   github.com/netanelSade1
Tel Aviv, Israel
"""


def test_regex_extract_pulls_contact_fields():
    d = regex_extract(CV)
    assert d["email"] == "netanelsbt@gmail.com"
    assert d["phone"].replace(" ", "") == "+97254-123-4567"
    assert d["linkedin_url"] == "https://linkedin.com/in/netanel-sade"
    assert d["github_url"] == "https://github.com/netanelSade1"


def test_regex_extract_absent_fields_omitted():
    d = regex_extract("just some text with no contacts")
    assert "email" not in d and "phone" not in d
    assert "linkedin_url" not in d and "github_url" not in d
