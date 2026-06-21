import json
from types import SimpleNamespace

from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences


def _job(title="Backend Engineer"):
    return Job(company_id="c", ats_job_id="1", title=title, url="https://x/1",
               location="Tel Aviv", description="build backend services")


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"score": 82, "reason": "strong backend fit"})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_openai_ranker_returns_match_results():
    client = _FakeClient()
    ranker = OpenAIRanker(client=client, model="gpt-4o")
    results = ranker.rank("backend cv", [_job()], Preferences(roles=["backend"]))
    assert len(results) == 1
    assert results[0].score == 82
    assert results[0].reason == "strong backend fit"
    assert results[0].stage == "llm"
    assert results[0].job_id == _job().id


def test_openai_ranker_injects_prefs_and_cv():
    client = _FakeClient()
    OpenAIRanker(client=client, model="gpt-4o").rank(
        "MY CV", [_job()], Preferences(roles=["backend"], max_years=3))
    msgs = client.chat.completions.calls[0]["messages"]
    blob = " ".join(m["content"] for m in msgs)
    assert "MY CV" in blob
    assert "backend" in blob.lower()
    assert "Backend Engineer" in blob


def test_rank_one_passes_card_and_district_into_prompt():
    import json
    from startup_agent.adapters.ranking.openai_ranker import OpenAIRanker
    from startup_agent.domain.models import Job
    captured = {}
    class _Comp:
        def create(self, model, response_format, messages):
            captured["user"] = messages[-1]["content"]
            class R:
                choices = [type("c", (), {"message": type("m", (), {"content": json.dumps({"score": 80, "reason": "good"})})})]
            return R()
    class _Client: chat = type("C", (), {"completions": _Comp()})()
    r = OpenAIRanker(model="gpt-4o-mini", client=_Client())
    job = Job(company_id="c", ats_job_id="1", title="Backend Eng", url="u", location="Tel Aviv")
    out = r.rank_one("CV", job, card={"tech_stack": ["Go"]}, district="center")
    assert out.score == 80
    assert "Go" in captured["user"] and "center" in captured["user"]
