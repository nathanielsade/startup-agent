from api import deps, llm_config


def test_build_profile_extractor_none_without_key():
    assert deps.build_profile_extractor_from("anthropic", "") is None


def test_build_profile_extractor_anthropic_and_openai():
    from startup_agent.adapters.profiling.claude_extractor import ClaudeProfileExtractor
    from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor
    assert isinstance(deps.build_profile_extractor_from("anthropic", "sk-x", "claude-opus-4-8"),
                      ClaudeProfileExtractor)
    assert isinstance(deps.build_profile_extractor_from("openai", "sk-x", "gpt-4o"),
                      OpenAIProfileExtractor)


def test_get_profile_extractor_prefers_in_memory_config():
    from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor
    llm_config.clear_config()
    llm_config.set_config("openai", "sk-mem", "gpt-4o")
    try:
        assert isinstance(deps.get_profile_extractor(), OpenAIProfileExtractor)
    finally:
        llm_config.clear_config()
