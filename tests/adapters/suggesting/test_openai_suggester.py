import json
from types import SimpleNamespace

from startup_agent.adapters.suggesting.openai_suggester import OpenAICvSuggester


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"max_years": 3, "roles": ["backend"], "seniority": ["mid"],
                              "title_include": ["engineer"]})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_openai_suggester_returns_preferences():
    client = _FakeClient()
    prefs = OpenAICvSuggester(client=client, model="gpt-4o").suggest("MY CV")
    assert prefs.max_years == 3
    assert prefs.roles == ["backend"]
    assert prefs.seniority == ["mid"]
    assert "MY CV" in str(client.chat.completions.calls[0])
