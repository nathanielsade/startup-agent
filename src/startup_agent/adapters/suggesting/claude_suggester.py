import anthropic
from pydantic import BaseModel

from startup_agent.adapters.suggesting.prompt import INSTRUCTIONS, to_preferences
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.cv_suggester import CvPreferenceSuggester


class _Suggestion(BaseModel):
    max_years: int | None = None
    roles: list[str] = []
    seniority: list[str] = []
    title_include: list[str] = []


class ClaudeCvSuggester(CvPreferenceSuggester):
    def __init__(self, api_key: str = "", model: str = "claude-opus-4-8",
                 client: object | None = None) -> None:
        self._client = client or (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self._model = model

    def suggest(self, cv_text: str) -> Preferences:
        message = self._client.messages.parse(
            model=self._model,
            max_tokens=600,
            system=[{"type": "text", "text": INSTRUCTIONS}],
            messages=[{"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nInfer the preferences."}],
            output_format=_Suggestion,
        )
        s = message.parsed_output
        return to_preferences({"max_years": s.max_years, "roles": s.roles,
                               "seniority": s.seniority, "title_include": s.title_include})
