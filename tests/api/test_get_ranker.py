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
