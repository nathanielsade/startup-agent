from startup_agent.config.settings import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    s = Settings()
    assert s.db_path == "jobs.db"
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.shortlist_size == 20


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setenv("SHORTLIST_SIZE", "5")
    s = Settings()
    assert s.db_path == "/tmp/custom.db"
    assert s.shortlist_size == 5
