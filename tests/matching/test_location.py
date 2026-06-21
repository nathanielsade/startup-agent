from startup_agent.matching.location import (
    classify_location, is_israel_relevant, region_allowed, Region,
)


def test_is_israel_relevant_keeps_israel_drops_foreign():
    assert is_israel_relevant("Tel Aviv") is True
    assert is_israel_relevant("Haifa") is True
    assert is_israel_relevant("Jerusalem") is True
    assert is_israel_relevant("Remote") is True              # location-agnostic remote
    assert is_israel_relevant("Kiryat Ono, Israel") is True
    assert is_israel_relevant("San Francisco") is False
    assert is_israel_relevant("New York, NY") is False
    assert is_israel_relevant("Anywhere in the US") is False
    assert is_israel_relevant(None) is False


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


def test_region_allowed_respects_chosen_districts():
    # center selected, remote on
    assert region_allowed("Tel Aviv", {"center"}, True) is True
    assert region_allowed("Haifa", {"center"}, True) is False          # north not selected
    assert region_allowed("Haifa", {"center", "north"}, True) is True  # north selected
    assert region_allowed("Jerusalem", {"jerusalem"}, True) is True
    # remote handling
    assert region_allowed("Remote", {"center"}, True) is True
    assert region_allowed("Remote", {"center"}, False) is False        # remote off
    assert region_allowed("India - Remote", {"center"}, True) is False # foreign-pinned remote
    # empty districts = no location constraint (keep all non-foreign)
    assert region_allowed("Haifa", set(), True) is True
    # unknown w/ israel marker kept; missing dropped
    assert region_allowed("Kiryat Ono, Israel", {"center"}, True) is True
    assert region_allowed(None, {"center"}, True) is False
