import json

from startup_agent.adapters.profiling.prompt import INSTRUCTIONS, to_profile
from startup_agent.domain.applicant_profile import ApplicantProfile
from startup_agent.ports.cv_profile_extractor import CvProfileExtractor


class OpenAIProfileExtractor(CvProfileExtractor):
    def __init__(self, api_key: str = "", model: str = "gpt-4o",
                 base_url: str = "", client: object | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)
        self._model = model

    def extract(self, cv_text: str) -> ApplicantProfile:
        completion = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"CANDIDATE CV:\n{cv_text}\n\nExtract the fields."},
            ],
        )
        data = json.loads(completion.choices[0].message.content)
        return to_profile(data)
