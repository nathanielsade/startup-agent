import json
from startup_agent.adapters.summarizing.openai_summarizer import OpenAIJobSummarizer


class _Msg:
    def __init__(self, content): self.message = type("M", (), {"content": content})
class _Resp:
    def __init__(self, content): self.choices = [_Msg(content)]
class _Completions:
    def __init__(self): self.calls = []
    def create(self, model, response_format, messages):
        self.calls.append((model, messages))
        return _Resp(json.dumps({"tech_stack": ["Go"], "required_years": 5,
                                 "seniority": "senior", "role_domain": "backend",
                                 "must_haves": [], "domain_industry": "fintech",
                                 "summary": "Senior Go backend."}))
class _Client:
    def __init__(self): self.chat = type("C", (), {"completions": _Completions()})()


def test_summarize_returns_structured_card_with_chosen_model():
    client = _Client()
    s = OpenAIJobSummarizer(model="gpt-4o-mini", client=client)
    card = s.summarize("Senior Backend Engineer", "Go, k8s, 5 years")
    assert card["required_years"] == 5 and card["role_domain"] == "backend"
    assert client.chat.completions.calls[0][0] == "gpt-4o-mini"
