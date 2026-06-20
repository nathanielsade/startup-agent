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


def build_ranker_from(provider: str, api_key: str, model: str = "", base_url: str = ""):
    """Build a Ranker from raw config, or None when no key is given."""
    if not api_key:
        return None
    if (provider or "anthropic").lower() == "openai":
        from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
        return OpenAIRanker(api_key=api_key, model=model or "gpt-4o", base_url=base_url)
    from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
    return ClaudeRanker(api_key=api_key, model=model or "claude-opus-4-8")


def build_ranker(settings):
    """Build a Ranker from .env settings, or None when no key is present."""
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        return build_ranker_from("openai", settings.openai_api_key,
                                 settings.openai_model, settings.openai_base_url)
    return build_ranker_from("anthropic", settings.anthropic_api_key, settings.llm_model)


def get_ranker():
    from api.llm_config import get_config
    cfg = get_config()
    if cfg is not None:
        return build_ranker_from(cfg["provider"], cfg["api_key"], cfg.get("model", ""))
    return build_ranker(get_settings())
