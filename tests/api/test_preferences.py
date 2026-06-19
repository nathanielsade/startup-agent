def test_get_preferences_returns_defaults_when_unset(client):
    resp = client.get("/api/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["districts"] == []
    assert body["include_remote"] is True


def test_put_then_get_preferences_round_trip(client):
    payload = {"districts": ["center", "north"], "include_remote": False,
               "max_years": 3, "posted_within_days": 30,
               "roles": ["backend"], "seniority": ["junior"],
               "title_include": ["engineer"], "exclude": ["senior"]}
    put = client.put("/api/preferences", json=payload)
    assert put.status_code == 200
    got = client.get("/api/preferences").json()
    assert got["districts"] == ["center", "north"]
    assert got["max_years"] == 3
