def test_llm_config_starts_unconfigured(client):
    resp = client.get("/api/llm-config")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "provider": None}


def test_put_then_get_reports_configured_without_key(client):
    put = client.put("/api/llm-config",
                     json={"provider": "anthropic", "api_key": "sk-secret-123"})
    assert put.status_code == 200
    body = put.json()
    assert body["configured"] is True and body["provider"] == "anthropic"
    got = client.get("/api/llm-config").json()
    assert got == {"configured": True, "provider": "anthropic"}
    # the key is NEVER echoed anywhere
    assert "sk-secret-123" not in put.text
    assert "api_key" not in got


def test_delete_clears(client):
    client.put("/api/llm-config", json={"provider": "openai", "api_key": "sk-x"})
    assert client.delete("/api/llm-config").json() == {"configured": False}
    assert client.get("/api/llm-config").json()["configured"] is False


def test_put_rejects_empty_key(client):
    resp = client.put("/api/llm-config", json={"provider": "anthropic", "api_key": ""})
    assert resp.status_code == 422
