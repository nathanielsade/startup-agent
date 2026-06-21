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


def test_inferred_required_years_prefers_explicit_card_then_regex_then_title():
    from startup_agent.matching.experience import inferred_required_years
    # explicit card value wins
    assert inferred_required_years("Backend Engineer", "needs 4 years", card_years=7) == 7
    # regex from description
    assert inferred_required_years("Backend Engineer", "5+ years required") == 5
    # title fallback when nothing stated
    assert inferred_required_years("Senior Backend Engineer", "great team") == 6
    assert inferred_required_years("Junior Developer", "great team") == 1
    assert inferred_required_years("Staff Engineer", None) == 8
    assert inferred_required_years("Backend Engineer", None) == 3   # no marker -> mid
