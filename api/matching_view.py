from startup_agent.config.preferences_loader import load_preferences
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository
from startup_agent.services.matching import SimilarityMatchingService

from api.schemas import JobMatch, to_job_match


def compute_matches(repo: JobRepository, embedder: Embedder,
                    preferences_path: str, threshold: float) -> list[JobMatch]:
    prefs = load_preferences(preferences_path)
    results = SimilarityMatchingService(
        repo=repo, embedder=embedder, preferences=prefs, threshold=threshold
    ).run()
    names = {c.id_hash: c.name for c in repo.get_companies()}
    return [to_job_match(job, score, names) for job, score in results]
