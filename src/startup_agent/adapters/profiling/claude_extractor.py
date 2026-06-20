import anthropic
from pydantic import BaseModel

from startup_agent.adapters.profiling.prompt import INSTRUCTIONS, to_profile
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.ports.cv_profile_extractor import CvProfileExtractor


class _Extraction(BaseModel):
    first_name: str = ""
    last_name: str = ""
    location: str = ""
    current_title: str = ""


class ClaudeProfileExtractor(CvProfileExtractor):
    def __init__(self, api_key: str = "", model: str = "claude-opus-4-8",
                 client: object | None = None) -> None:
        self._client = client or (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self._model = model

    def extract(self, cv_text: str) -> ApplicantProfile:
        message = self._client.messages.parse(
            model=self._model,
            max_tokens=400,
            system=[{"type": "text", "text": INSTRUCTIONS}],
            messages=[{"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nExtract the fields."}],
            output_format=_Extraction,
        )
        s = message.parsed_output
        return to_profile({"first_name": s.first_name, "last_name": s.last_name,
                           "location": s.location, "current_title": s.current_title})
