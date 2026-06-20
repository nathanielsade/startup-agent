from types import SimpleNamespace

from startup_agent.adapters.suggesting.claude_suggester import ClaudeCvSuggester


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=SimpleNamespace(
            max_years=3, roles=["backend", "ai"], seniority=["junior", "mid"],
            title_include=["engineer"]))


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_claude_suggester_returns_preferences_from_cv():
    client = _FakeClient()
    prefs = ClaudeCvSuggester(client=client, model="claude-opus-4-8").suggest("MY CV TEXT")
    assert prefs.max_years == 3
    assert prefs.roles == ["backend", "ai"]
    assert prefs.seniority == ["junior", "mid"]
    assert prefs.title_include == ["engineer"]
    # CV text reached the prompt
    blob = str(client.messages.calls[0])
    assert "MY CV TEXT" in blob
