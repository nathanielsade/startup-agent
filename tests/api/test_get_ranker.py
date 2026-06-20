from startup_agent.config.settings import Settings
from api.deps import build_ranker


def test_build_ranker_none_without_key():
    s = Settings(llm_provider="anthropic", anthropic_api_key="")
    assert build_ranker(s) is None


def test_build_ranker_anthropic_with_key():
    from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
    s = Settings(llm_provider="anthropic", anthropic_api_key="sk-test", llm_model="claude-opus-4-8")
    assert isinstance(build_ranker(s), ClaudeRanker)


def test_build_ranker_openai_with_key():
    from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
    s = Settings(llm_provider="openai", openai_api_key="sk-test", openai_model="gpt-4o")
    assert isinstance(build_ranker(s), OpenAIRanker)


def test_get_ranker_prefers_in_memory_config():
    from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
    from api import deps, llm_config
    llm_config.clear_config()
    # .env settings say anthropic with NO key (would be None)…
    # …but the in-memory store has an openai key → that wins.
    llm_config.set_config("openai", "sk-mem", "gpt-4o")
    try:
        assert isinstance(deps.get_ranker(), OpenAIRanker)
    finally:
        llm_config.clear_config()


def test_build_ranker_from_none_without_key():
    from api.deps import build_ranker_from
    assert build_ranker_from("anthropic", "") is None
