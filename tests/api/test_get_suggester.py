from api import deps, llm_config


def test_build_suggester_none_without_key():
    assert deps.build_suggester_from("anthropic", "") is None


def test_build_suggester_anthropic_and_openai():
    from startup_agent.adapters.suggesting.claude_suggester import ClaudeCvSuggester
    from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester
    assert isinstance(deps.build_suggester_from("anthropic", "sk-x", "claude-opus-4-8"), ClaudeCvSuggester)
    assert isinstance(deps.build_suggester_from("openai", "sk-x", "gpt-4o"), OpenAICvSuggester)


def test_get_suggester_prefers_in_memory_config():
    from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester
    llm_config.clear_config()
    llm_config.set_config("openai", "sk-mem", "gpt-4o")
    try:
        assert isinstance(deps.get_suggester(), OpenAICvSuggester)
    finally:
        llm_config.clear_config()
