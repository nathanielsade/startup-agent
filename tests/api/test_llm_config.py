from fastapi.testclient import TestClient

from api import deps
from api.llm_config import clear_config
from api.main import app
from startup_agent.config.settings import Settings

client = TestClient(app)


def teardown_function(_):
    clear_config()
    app.dependency_overrides.clear()


def test_reports_server_side_openai_key_as_configured():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        llm_provider="openai", openai_api_key="sk-test")
    r = client.get("/api/llm-config").json()
    assert r == {"configured": True, "provider": "openai"}


def test_reports_not_configured_when_no_key_anywhere():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        llm_provider="openai", openai_api_key="", anthropic_api_key="")
    r = client.get("/api/llm-config").json()
    assert r == {"configured": False, "provider": None}


def test_user_pasted_key_takes_precedence():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        llm_provider="openai", openai_api_key="")
    client.put("/api/llm-config", json={"provider": "anthropic", "api_key": "sk-user"})
    r = client.get("/api/llm-config").json()
    assert r == {"configured": True, "provider": "anthropic"}
