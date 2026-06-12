from startup_agent.config.preferences_loader import load_preferences


def test_loads_preferences_yaml():
    prefs = load_preferences("data/preferences.yaml")
    assert "Senior" in prefs.exclude
    assert any("Full Stack" in r for r in prefs.roles)


def test_loads_title_include():
    from startup_agent.config.preferences_loader import load_preferences
    prefs = load_preferences("data/preferences.yaml")
    assert "engineer" in prefs.title_include
