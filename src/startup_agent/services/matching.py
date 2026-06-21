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

    @staticmethod
    def _job_text(job: Job) -> str:
        return f"{job.title}\n{(job.description or '')[:2000]}"

    def _vectors_for(self, jobs: list[Job]) -> dict[str, list[float]]:
        """Return id -> embedding for every job, reusing cached vectors and
        batch-embedding only the un-cached ones in a single model call."""
        vectors: dict[str, list[float]] = {}
        to_embed: list[Job] = []
        for job in jobs:
            cached = self._repo.get_job_embedding(job.id)
            if cached is not None:
                vectors[job.id] = from_bytes(cached)
            else:
                to_embed.append(job)
        if to_embed:
            new_vectors = self._embedder.embed([self._job_text(j) for j in to_embed])
            for job, vector in zip(to_embed, new_vectors):
                vectors[job.id] = vector
                self._repo.set_job_embedding(job.id, to_bytes(vector))
        return vectors

    def run(self) -> list[tuple[Job, float]]:
        cv = self._repo.get_cv()
        if cv is None or cv["embedding"] is None:
            raise RuntimeError("No CV loaded. Run 'startup-agent load-cv --path <pdf>' first.")
        cv_vector = from_bytes(cv["embedding"])

        candidates = [j for j in self._repo.get_jobs()
                      if passes_prefilter(j, self._preferences)]
        vectors = self._vectors_for(candidates)
        scored: list[tuple[Job, float]] = []
        for job in candidates:
            base = cosine(cv_vector, vectors[job.id])
            score = soft_adjust(job, self._preferences, base)
            if score >= self._threshold:
                scored.append((job, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        logger.info("match_complete", candidates=len(candidates), matched=len(scored))
        return scored
