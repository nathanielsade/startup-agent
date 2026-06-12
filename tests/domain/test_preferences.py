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
