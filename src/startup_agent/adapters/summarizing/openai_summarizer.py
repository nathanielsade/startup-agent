import json

from startup_agent.adapters.summarizing.prompt import INSTRUCTIONS

_KEYS = ("tech_stack", "required_years", "seniority", "role_domain",
         "must_haves", "domain_industry", "summary")


class OpenAIJobSummarizer:
    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini",
                 base_url: str = "", client: object | None = None) -> None:
        self._api_key, self._base_url, self._model = api_key, base_url, model
        self._client = client

    def _ensure(self):
        if self._client is None:
            from openai import OpenAI
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def summarize(self, title: str, description: str) -> dict:
        resp = self._ensure().chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"TITLE: {title}\n\nPOSTING:\n{description[:4000]}"},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return {k: data.get(k) for k in _KEYS}
