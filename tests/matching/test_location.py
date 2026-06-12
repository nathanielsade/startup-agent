from startup_agent.matching.location import classify_location, location_allowed, Region


def test_classifies_regions():
    assert classify_location("Tel Aviv-Yafo, Tel Aviv District, Israel") is Region.CENTER
    assert classify_location("Herzliya") is Region.CENTER
    assert classify_location("Haifa, Israel") is Region.NORTH
    assert classify_location("Yokneam") is Region.NORTH
    assert classify_location("Beer Sheva") is Region.SOUTH
    assert classify_location("Jerusalem") is Region.JERUSALEM
    assert classify_location("US Remote") is Region.REMOTE
    assert classify_location("Remote - Israel") is Region.REMOTE
    assert classify_location("London, UK") is Region.UNKNOWN
    assert classify_location(None) is Region.UNKNOWN


def test_location_allowed_rule():
    assert location_allowed("Tel Aviv") is True       # center
    assert location_allowed("Remote") is True          # remote always ok
    assert location_allowed("Haifa") is False          # north
    assert location_allowed("Beer Sheva") is False     # south
    assert location_allowed("Jerusalem") is False      # excluded
    assert location_allowed("London") is True          # unknown -> keep (don't miss)
    assert location_allowed(None) is True              # missing -> keep
