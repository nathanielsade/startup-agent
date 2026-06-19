import structlog

from startup_agent.adapters.embedding.serialization import from_bytes, to_bytes
from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences
from startup_agent.matching.prefilter import passes_prefilter
from startup_agent.matching.similarity import cosine
from startup_agent.matching.soft_score import soft_adjust
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()


class SimilarityMatchingService:
    def __init__(self, repo: JobRepository, embedder: Embedder,
                 preferences: Preferences, threshold: float) -> None:
        self._repo = repo
        self._embedder = embedder
        self._preferences = preferences
        self._threshold = threshold

    def _job_vector(self, job: Job) -> list[float]:
        cached = self._repo.get_job_embedding(job.id)
        if cached is not None:
            return from_bytes(cached)
        text = f"{job.title}\n{(job.description or '')[:2000]}"
        vector = self._embedder.embed([text])[0]
        self._repo.set_job_embedding(job.id, to_bytes(vector))
        return vector

    def run(self) -> list[tuple[Job, float]]:
        cv = self._repo.get_cv()
        if cv is None or cv["embedding"] is None:
            raise RuntimeError("No CV loaded. Run 'startup-agent load-cv --path <pdf>' first.")
        cv_vector = from_bytes(cv["embedding"])

        candidates = [j for j in self._repo.get_jobs()
                      if passes_prefilter(j, self._preferences)]
        scored: list[tuple[Job, float]] = []
        for job in candidates:
            base = cosine(cv_vector, self._job_vector(job))
            score = soft_adjust(job, self._preferences, base)
            if score >= self._threshold:
                scored.append((job, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        logger.info("match_complete", candidates=len(candidates), matched=len(scored))
        return scored
