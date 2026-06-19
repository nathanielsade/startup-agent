from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.config.settings import Settings
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository


def get_settings() -> Settings:
    return Settings()


def get_repo() -> JobRepository:
    repo = SQLiteJobRepository(get_settings().db_path)
    repo.init_schema()
    return repo


def get_embedder() -> Embedder:
    return LocalEmbedder(get_settings().embedding_model)


def get_factory() -> ATSAdapterFactory:
    return ATSAdapterFactory()


def build_ranker(settings):
    """Return a configured Ranker, or None when no key is present."""
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        if not settings.openai_api_key:
            return None
        from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
        return OpenAIRanker(api_key=settings.openai_api_key, model=settings.openai_model,
                            base_url=settings.openai_base_url)
    if not settings.anthropic_api_key:
        return None
    from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
    return ClaudeRanker(api_key=settings.anthropic_api_key, model=settings.llm_model)


def get_ranker():
    return build_ranker(get_settings())
