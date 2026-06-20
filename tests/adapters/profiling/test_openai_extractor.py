import json
from types import SimpleNamespace

from startup_agent.adapters.profiling.openai_extractor import OpenAIProfileExtractor


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"first_name": "Netanel", "last_name": "Sade",
                              "location": "Tel Aviv", "current_title": "Backend Engineer"})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_openai_extractor_returns_profile():
    client = _FakeClient()
    p = OpenAIProfileExtractor(client=client, model="gpt-4o").extract("MY CV")
    assert p.first_name == "Netanel" and p.current_title == "Backend Engineer"
    assert "MY CV" in str(client.chat.completions.calls[0])
