import anthropic
from pydantic import BaseModel, Field

from startup_agent.domain.models import Job, MatchResult
from startup_agent.ports.ranker import Ranker

_SYSTEM = (
    "You are a job-matching assistant. Given a candidate's CV and a single job "
    "posting, score how well the job fits the candidate from 0 to 100 and give a "
    "one-line reason (max ~20 words). Weigh role, seniority, skills, and domain. "
    "Be strict: 70+ means a genuinely strong fit worth applying to; 40-69 a "
    "stretch; below 40 a poor fit."
)


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

    def rank(self, cv_text: str, jobs: list[Job]) -> list[MatchResult]:
        results: list[MatchResult] = []
        for job in jobs:
            job_text = (
                f"Title: {job.title}\n"
                f"Location: {job.location or 'n/a'}\n\n"
                f"{(job.description or '')[:4000]}"
            )
            message = self._client.messages.parse(
                model=self._model,
                max_tokens=1000,
                system=[
                    {"type": "text", "text": _SYSTEM},
                    {"type": "text", "text": f"CANDIDATE CV:\n{cv_text}",
                     "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user",
                           "content": f"JOB POSTING:\n{job_text}\n\nScore this job for the candidate."}],
                output_format=_Score,
            )
            parsed = message.parsed_output
            results.append(MatchResult(job_id=job.id, score=parsed.score,
                                       reason=parsed.reason, stage="llm"))
        return results
