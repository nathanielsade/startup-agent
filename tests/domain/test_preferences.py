from startup_agent.domain.preferences import Preferences


def test_preferences_defaults_and_parsing():
    p = Preferences(roles=["backend", "ai"], seniority=["mid", "senior"],
                    locations=["Tel Aviv", "Remote"], must_have=["python"], exclude=["unpaid"])
    assert "backend" in p.roles
    assert p.exclude == ["unpaid"]


def test_preferences_empty_is_valid():
    p = Preferences()
    assert p.roles == []
    assert p.locations == []


def test_structured_preference_fields_have_defaults():
    from startup_agent.domain.preferences import Preferences
    p = Preferences()
    assert p.districts == []
    assert p.include_remote is True
    assert p.max_years is None
    assert p.posted_within_days is None
    assert p.roles == []
    assert p.seniority == []
    assert p.title_include == []
    assert p.exclude == []


def test_preferences_accepts_structured_values():
    from startup_agent.domain.preferences import Preferences
    p = Preferences(districts=["center", "north"], include_remote=False,
                    max_years=3, posted_within_days=30,
                    roles=["backend", "ai"], seniority=["junior", "mid"],
                    title_include=["engineer"], exclude=["senior"])
    assert p.districts == ["center", "north"]
    assert p.max_years == 3
