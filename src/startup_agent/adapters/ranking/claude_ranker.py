import anthropic
from pydantic import BaseModel, Field

from startup_agent.adapters.ranking.prompt import INSTRUCTIONS, job_text, preferences_clause
from startup_agent.domain.models import Job, MatchResult
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.ranker import Ranker


class _Score(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


class ClaudeRanker(Ranker):
    def __init__(self, api_key: str = "", model: str = "claude-opus-4-8",
                 client: object | None = None) -> None:
        self._client = client or (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self._model = model

    def rank(self, cv_text: str, jobs: list[Job],
             preferences: Preferences | None = None) -> list[MatchResult]:
        instructions = INSTRUCTIONS
        clause = preferences_clause(preferences)
        if clause:
            instructions = f"{INSTRUCTIONS}\n\n{clause}"
        results: list[MatchResult] = []
        for job in jobs:
            message = self._client.messages.parse(
                model=self._model,
                max_tokens=1000,
                system=[
                    {"type": "text", "text": instructions},
                    {"type": "text", "text": f"CANDIDATE CV:\n{cv_text}",
                     "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user",
                           "content": f"JOB POSTING:\n{job_text(job)}\n\nScore this job for the candidate."}],
                output_format=_Score,
            )
            parsed = message.parsed_output
            results.append(MatchResult(job_id=job.id, score=parsed.score,
                                       reason=parsed.reason, stage="llm"))
        return results
