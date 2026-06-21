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


def _auto_llm(settings):
    """Auto-pick the server LLM (provider, api_key, model, base_url) from whichever
    key is set — preferring OpenAI + the cheap rerank model (token-efficient). This
    means the app 'just works' with the key present, no LLM_PROVIDER env needed.
    provider is None when no key is configured."""
    if settings.openai_api_key:
        return "openai", settings.openai_api_key, settings.llm_rerank_model, settings.openai_base_url
    if settings.anthropic_api_key:
        return "anthropic", settings.anthropic_api_key, settings.llm_model, ""
    return None, "", "", ""


def build_ranker(settings):
    """Build a Ranker from .env settings, or None when no key is present."""
    provider, key, model, base = _auto_llm(settings)
    return build_ranker_from(provider or "anthropic", key, model, base)


def get_ranker():
    from api.llm_config import get_config
    cfg = get_config()
    if cfg is not None:
        return build_ranker_from(cfg["provider"], cfg["api_key"], cfg.get("model", ""))
    return build_ranker(get_settings())


def get_rerank_ranker():
    s = get_settings()
    return build_ranker_from("openai", s.openai_api_key, s.llm_rerank_model, s.openai_base_url)


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
    provider, key, model, base = _auto_llm(get_settings())
    return build_suggester_from(provider or "anthropic", key, model, base)


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
    provider, key, model, base = _auto_llm(get_settings())
    return build_profile_extractor_from(provider or "anthropic", key, model, base)
