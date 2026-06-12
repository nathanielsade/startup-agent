import structlog

from startup_agent.domain.models import Job, MatchResult, RunReport
from startup_agent.domain.preferences import Preferences
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.ranker import Ranker
from startup_agent.ports.repository import JobRepository
from startup_agent.services.matching import SimilarityMatchingService

logger = structlog.get_logger()


class HybridMatchingService:
    def __init__(self, repo: JobRepository, embedder: Embedder, ranker: Ranker,
                 preferences: Preferences, sim_threshold: float,
                 llm_threshold: int) -> None:
        self._repo = repo
        self._ranker = ranker
        self._llm_threshold = llm_threshold
        self._similarity = SimilarityMatchingService(
            repo=repo, embedder=embedder, preferences=preferences, threshold=sim_threshold
        )

    def run(self) -> list[tuple[Job, MatchResult]]:
        candidates = [job for job, _score in self._similarity.run()]
        if not candidates:
            self._repo.record_run(RunReport(jobs_matched=0))
            return []

        cv = self._repo.get_cv()
        if cv is None:
            raise RuntimeError("No CV loaded. Run 'startup-agent load-cv --path <pdf>' first.")

        scored = self._ranker.rank(cv["text"], candidates)
        run_id = self._repo.record_run(RunReport(jobs_fetched=len(candidates),
                                                  jobs_matched=len(scored)))
        self._repo.record_matches(run_id, scored)

        by_id = {job.id: job for job in candidates}
        kept = sorted(
            (m for m in scored if m.score >= self._llm_threshold),
            key=lambda m: m.score, reverse=True,
        )
        logger.info("hybrid_match_complete", candidates=len(candidates), kept=len(kept))
        return [(by_id[m.job_id], m) for m in kept if m.job_id in by_id]
