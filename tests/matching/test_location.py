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
    assert location_allowed("Tel Aviv") is True
    assert location_allowed("Tel Aviv-Yafo, Tel Aviv District, Israel") is True
    assert location_allowed("Kiryat Ono, Israel") is True   # unlisted Israeli city, has "israel"
    assert location_allowed("Remote") is True
    assert location_allowed("Remote - EMEA") is True
    assert location_allowed("Haifa") is False
    assert location_allowed("Beer Sheva") is False
    assert location_allowed("Jerusalem") is False
    assert location_allowed("Dublin") is False              # foreign -> drop
    assert location_allowed("United States") is False        # foreign -> drop
    assert location_allowed("London") is False
    assert location_allowed(None) is False                   # missing -> drop


def test_foreign_remote_dropped_but_israel_and_bare_remote_kept():
    # foreign-pinned remote -> drop (any place name, no country list needed)
    assert location_allowed("India- Remote") is False
    assert location_allowed("Australia - Remote") is False
    assert location_allowed("United Kingdom - Remote") is False
    assert location_allowed("Remote (US)") is False
    assert location_allowed("Bulgaria- Remote") is False
    assert location_allowed("Ankara, Türkiye - Remote") is False
    assert location_allowed("Remote - Europe") is False
    assert location_allowed("Washington, DC - Remote") is False
    assert location_allowed("Remote U.S.") is False
    # Israel / location-agnostic remote -> keep
    assert location_allowed("Remote - Israel") is True
    assert location_allowed("Tel Aviv (Remote)") is True
    assert location_allowed("Remote") is True            # bare remote (could be global/IL)
    assert location_allowed("Fully Remote") is True
    assert location_allowed("100% Remote") is True
    assert location_allowed("Remote - EMEA") is True     # EMEA includes Israel
