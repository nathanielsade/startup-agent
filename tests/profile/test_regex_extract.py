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


def test_phone_skips_date_ranges():
    # an experience section full of year ranges, no real phone → no phone field
    cv = "Senior Engineer 2019 - 2023\nJunior Dev 2018-2022 (4 years)\n"
    assert "phone" not in regex_extract(cv)


def test_phone_found_after_date_ranges():
    cv = "Experience 2019 - 2023\nContact: +972 54-123-4567\n"
    assert regex_extract(cv)["phone"].replace(" ", "") == "+97254-123-4567"


def test_local_10_digit_phone_extracted():
    assert regex_extract("Phone 054-123-4567")["phone"] == "054-123-4567"


def test_email_trailing_dot_stripped():
    assert regex_extract("reach me at a@b.io.")["email"] == "a@b.io"
