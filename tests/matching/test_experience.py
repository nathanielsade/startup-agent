from startup_agent.matching.experience import required_years


def test_extracts_minimum_years():
    assert required_years("We need 5+ years of experience in backend") == 5
    assert required_years("Minimum 7 years experience required") == 7
    assert required_years("3-5 years of experience") == 3       # lower bound of a range
    assert required_years("at least 8 years") == 8


def test_no_years_returns_none():
    assert required_years("Great backend role, join us!") is None
    assert required_years(None) is None
    assert required_years("") is None
