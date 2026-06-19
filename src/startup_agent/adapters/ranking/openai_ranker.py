import json

from startup_agent.adapters.ranking.prompt import INSTRUCTIONS, job_text, preferences_clause
from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.ranker import Ranker


class OpenAIRanker(Ranker):
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

    def rank(self, cv_text: str, jobs: list[Job],
             preferences: Preferences | None = None) -> list[MatchResult]:
        instructions = INSTRUCTIONS
        clause = preferences_clause(preferences)
        if clause:
            instructions = f"{INSTRUCTIONS}\n\n{clause}"
        instructions += (
            '\n\nRespond ONLY with JSON: {"score": <int 0-100>, "reason": "<one line>"}'
        )
        results: list[MatchResult] = []
        for job in jobs:
            completion = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user",
                     "content": f"CANDIDATE CV:\n{cv_text}\n\nJOB POSTING:\n{job_text(job)}\n\nScore this job."},
                ],
            )
            data = json.loads(completion.choices[0].message.content)
            score = max(0, min(100, int(data.get("score", 0))))
            results.append(MatchResult(job_id=job.id, score=score,
                                       reason=str(data.get("reason", "")), stage="llm"))
        return results
