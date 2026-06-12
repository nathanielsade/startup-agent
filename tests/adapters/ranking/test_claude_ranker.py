from types import SimpleNamespace

from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
from startup_agent.domain.models import Job


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        # echo a deterministic score; reason references the title in the user turn
        return SimpleNamespace(parsed_output=SimpleNamespace(score=88, reason="strong backend fit"))


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def _job(title):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location="Tel Aviv", description="build backend services")


def test_claude_ranker_returns_match_results():
    client = _FakeClient()
    ranker = ClaudeRanker(client=client, model="claude-opus-4-8")
    results = ranker.rank("backend engineer cv", [_job("Backend Engineer"), _job("Platform Engineer")])

    assert len(results) == 2
    assert results[0].score == 88
    assert results[0].reason == "strong backend fit"
    assert results[0].stage == "llm"
    assert results[0].job_id == _job("Backend Engineer").id


def test_claude_ranker_caches_cv_in_system_block():
    client = _FakeClient()
    ranker = ClaudeRanker(client=client, model="claude-opus-4-8")
    ranker.rank("MY CV TEXT", [_job("Backend Engineer")])

    kw = client.messages.calls[0]
    assert kw["model"] == "claude-opus-4-8"
    # CV goes in a cached system block; the job goes in the user turn
    system_texts = [b["text"] for b in kw["system"]]
    assert any("MY CV TEXT" in t for t in system_texts)
    assert any(b.get("cache_control") == {"type": "ephemeral"} for b in kw["system"])
    assert "Backend Engineer" in kw["messages"][0]["content"]
