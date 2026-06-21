from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.config.settings import Settings
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.factories.embedder_factory import build_embedder
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository


def get_settings() -> Settings:
    return Settings()


def get_repo() -> JobRepository:
    repo = SQLiteJobRepository(get_settings().db_path)
    repo.init_schema()
    return repo


def get_embedder() -> Embedder:
    return build_embedder(get_settings())


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


def build_suggester_from(provider: str, api_key: str, model: str = "", base_url: str = ""):
    """Build a CvPreferenceSuggester from raw config, or None when no key is given."""
    if not api_key:
        return None
    if (provider or "anthropic").lower() == "openai":
        from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester
        return OpenAICvSuggester(api_key=api_key, model=model or "gpt-4o", base_url=base_url)
    from startup_agent.adapters.suggesting.claude_suggester import ClaudeCvSuggester
    return ClaudeCvSuggester(api_key=api_key, model=model or "claude-opus-4-8")


def get_suggester():
    from api.llm_config import get_config
    cfg = get_config()
    if cfg is not None:
        return build_suggester_from(cfg["provider"], cfg["api_key"], cfg.get("model", ""))
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        return build_suggester_from("openai", settings.openai_api_key,
                                    settings.openai_model, settings.openai_base_url)
    return build_suggester_from("anthropic", settings.anthropic_api_key, settings.llm_model)


def build_profile_extractor_from(provider: str, api_key: str, model: str = "", base_url: str = ""):
    """Build a CvProfileExtractor from raw config, or None when no key is given."""
    if not api_key:
        return None
    if (provider or "anthropic").lower() == "openai":
        from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor
        return OpenAIProfileExtractor(api_key=api_key, model=model or "gpt-4o", base_url=base_url)
    from startup_agent.adapters.profiling.claude_extractor import ClaudeProfileExtractor
    return ClaudeProfileExtractor(api_key=api_key, model=model or "claude-opus-4-8")


def get_profile_extractor():
    from api.llm_config import get_config
    cfg = get_config()
    if cfg is not None:
        return build_profile_extractor_from(cfg["provider"], cfg["api_key"], cfg.get("model", ""))
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").lower()
    if provider == "openai":
        return build_profile_extractor_from("openai", settings.openai_api_key,
                                            settings.openai_model, settings.openai_base_url)
    return build_profile_extractor_from("anthropic", settings.anthropic_api_key, settings.llm_model)
