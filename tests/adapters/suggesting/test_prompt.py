from startup_agent.adapters.suggesting.prompt import to_preferences


def test_to_preferences_keeps_only_inferable_and_drops_out_of_vocab():
    p = to_preferences({"max_years": 3, "roles": ["backend", "ai", "blockchain"],
                        "seniority": ["junior", "wizard"], "title_include": ["engineer"]})
    assert p.max_years == 3
    assert p.roles == ["backend", "ai"]          # "blockchain" dropped (out of vocab)
    assert p.seniority == ["junior"]             # "wizard" dropped
    assert p.title_include == ["engineer"]
    # pure-preference fields stay at defaults (suggester never sets them)
    assert p.districts == [] and p.include_remote is True and p.posted_within_days is None


def test_to_preferences_tolerates_missing_fields():
    p = to_preferences({})
    assert p.max_years is None and p.roles == [] and p.seniority == []


def test_to_preferences_drops_non_positive_max_years():
    # max_years is a hard filter; 0 or negative would hide every job → treat as unset
    assert to_preferences({"max_years": 0}).max_years is None
    assert to_preferences({"max_years": -3}).max_years is None
