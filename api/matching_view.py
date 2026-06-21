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
    companies = repo.get_companies()
    names = {c.id_hash: c.name for c in companies}
    links = {c.id_hash: c.linkedin_url for c in companies}
    sites = {c.id_hash: c.website for c in companies}
    return [to_job_match(job, score, names, company_links=links, company_websites=sites)
            for job, score in results]


def match_pairs(repo, embedder, preferences_path, threshold):
    prefs = _load_prefs(repo, preferences_path)
    return SimilarityMatchingService(
        repo=repo, embedder=embedder, preferences=prefs, threshold=threshold
    ).run()
