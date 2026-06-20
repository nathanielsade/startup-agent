from types import SimpleNamespace

from startup_agent.adapters.profiling.claude_extractor import ClaudeProfileExtractor


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=SimpleNamespace(
            first_name="Netanel", last_name="Sade",
            location="Tel Aviv", current_title="Backend Engineer"))


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_claude_extractor_returns_profile_from_cv():
    client = _FakeClient()
    p = ClaudeProfileExtractor(client=client, model="claude-opus-4-8").extract("MY CV TEXT")
    assert p.first_name == "Netanel" and p.last_name == "Sade"
    assert p.location == "Tel Aviv" and p.current_title == "Backend Engineer"
    assert "MY CV TEXT" in str(client.messages.calls[0])
