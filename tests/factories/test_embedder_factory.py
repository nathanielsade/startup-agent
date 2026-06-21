from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.embedding.openai_embedder import OpenAIEmbedder
from startup_agent.config.settings import Settings
from startup_agent.factories.embedder_factory import build_embedder


def test_local_provider_builds_local_embedder():
    s = Settings(embedding_provider="local")
    assert isinstance(build_embedder(s), LocalEmbedder)


def test_openai_provider_builds_openai_embedder():
    s = Settings(embedding_provider="openai", openai_api_key="sk-test")
    assert isinstance(build_embedder(s), OpenAIEmbedder)


def test_active_embedding_model_tracks_provider():
    assert Settings(embedding_provider="local").active_embedding_model == "BAAI/bge-small-en-v1.5"
    assert Settings(embedding_provider="openai").active_embedding_model == "text-embedding-3-small"
