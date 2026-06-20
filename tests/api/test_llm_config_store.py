from api import llm_config


def test_store_set_get_clear():
    llm_config.clear_config()
    assert llm_config.get_config() is None
    llm_config.set_config("anthropic", "sk-test", "claude-opus-4-8")
    cfg = llm_config.get_config()
    assert cfg == {"provider": "anthropic", "api_key": "sk-test", "model": "claude-opus-4-8"}
    llm_config.clear_config()
    assert llm_config.get_config() is None
