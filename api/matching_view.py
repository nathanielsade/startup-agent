from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository
from startup_agent.services.matching import SimilarityMatchingService

from api.schemas import JobMatch, to_job_match


def _load_prefs(repo, preferences_path):
    stored = repo.get_preferences()
    if stored is not None:
        return stored
    from startup_agent.config.preferences_loader import load_preferences
    return load_preferences(preferences_path)


def compute_matches(repo: JobRepository, embedder: Embedder,
                    preferences_path: str, threshold: float) -> list[JobMatch]:
    prefs = _load_prefs(repo, preferences_path)
    results = SimilarityMatchingService(
        repo=repo, embedder=embedder, preferences=prefs, threshold=threshold
    ).run()
    names = {c.id_hash: c.name for c in repo.get_companies()}
    return [to_job_match(job, score, names) for job, score in results]


def match_pairs(repo, embedder, preferences_path, threshold):
    prefs = _load_prefs(repo, preferences_path)
    return SimilarityMatchingService(
        repo=repo, embedder=embedder, preferences=prefs, threshold=threshold
    ).run()
