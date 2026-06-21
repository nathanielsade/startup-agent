from startup_agent.adapters.profiling.prompt import to_profile


def test_to_profile_keeps_only_judgment_fields():
    p = to_profile({"first_name": "Netanel", "last_name": "Sade",
                    "location": "Tel Aviv", "current_title": "Backend Engineer",
                    "email": "x@y.com"})  # email ignored — regex owns contact fields
    assert p.first_name == "Netanel" and p.last_name == "Sade"
    assert p.location == "Tel Aviv" and p.current_title == "Backend Engineer"
    assert p.email == "" and p.phone == ""


def test_to_profile_tolerates_missing_and_coerces_str():
    p = to_profile({"first_name": 5})
    assert p.first_name == "5" and p.last_name == "" and p.location == ""


def test_to_profile_extracts_years_experience():
    from startup_agent.adapters.profiling.prompt import to_profile
    p = to_profile({"first_name": "A", "years_experience": 4})
    assert p.years_experience == 4

def test_to_profile_years_none_when_absent_or_unparseable():
    from startup_agent.adapters.profiling.prompt import to_profile
    assert to_profile({"first_name": "A"}).years_experience is None
    assert to_profile({"years_experience": "lots"}).years_experience is None
