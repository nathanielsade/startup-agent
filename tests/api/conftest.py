import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import deps
from startup_agent.config.settings import Settings


@pytest.fixture(autouse=True)
def _clear_llm_config():
    from api import llm_config
    llm_config.clear_config()
    yield
    llm_config.clear_config()


class FakeEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "backend" in t.lower() else [0.0, 1.0] for t in texts]


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "web.db"),
                    preferences_path="data/preferences.yaml",
                    match_threshold=0.3)


@pytest.fixture
def client(settings):
    app.dependency_overrides[deps.get_settings] = lambda: settings
    app.dependency_overrides[deps.get_embedder] = lambda: FakeEmbedder()
    yield TestClient(app)
    app.dependency_overrides.clear()
