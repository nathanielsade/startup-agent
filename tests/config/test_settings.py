from startup_agent.config.settings import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    s = Settings()
    assert s.db_path == "jobs.db"
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.shortlist_size == 20


def test_settings_match_defaults(monkeypatch):
    monkeypatch.delenv("MATCH_THRESHOLD", raising=False)
    from startup_agent.config.settings import Settings
    s = Settings()
    assert s.match_threshold == 0.30
    assert s.preferences_path == "data/preferences.yaml"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setenv("SHORTLIST_SIZE", "5")
    s = Settings()
    assert s.db_path == "/tmp/custom.db"
    assert s.shortlist_size == 5


def test_settings_llm_defaults(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    from startup_agent.config.settings import Settings
    s = Settings()
    assert s.llm_model == "claude-opus-4-8"
    assert s.llm_threshold == 70


def test_settings_llm_provider_defaults(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    from startup_agent.config.settings import Settings
    s = Settings()
    assert s.llm_provider == "anthropic"
    assert s.llm_recent_hours == 24
    assert s.openai_model == "gpt-4o"
