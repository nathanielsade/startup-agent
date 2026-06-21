import structlog

from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.services.ingestion import IngestionService

logger = structlog.get_logger()


def run_batch(repo, factory, embedder, *, model: str,
              seed_path: str | None = None, progress=None) -> dict:
    """The every-N-hours batch: (re)load companies, fetch jobs, embed the new ones,
    retire vanished jobs. Writes everything to the shared store (Postgres in cloud).

    Designed for injection: `repo` (PostgresJobRepository), `factory`
    (ATSAdapterFactory), `embedder` (LocalEmbedder) are all passed in, so tests run
    with fakes and no network/model.
    """
    run_start = repo.now()  # DB clock, so retire comparisons use a single clock

    if seed_path:
        from startup_agent.companies.loader import load_companies_from_seed
        for company in load_companies_from_seed(seed_path):
            repo.upsert_company(company)

    # 1. fetch + upsert jobs (upsert stamps last_seen_at / active=TRUE)
    report = IngestionService(repo, factory).run(progress=progress)

    # 2. embed jobs that lack an up-to-date vector — one batched encode call
    pending = repo.jobs_needing_embedding(model)
    if pending:
        vectors = embedder.embed([text for _, text in pending])
        for (job_id, _), vector in zip(pending, vectors):
            repo.store_embedding(job_id, to_bytes(vector), model)

    # 3. retire jobs no longer returned (soft-delete; user history preserved)
    retired = repo.retire_stale(run_start)

    result = {"companies": report.companies_count, "fetched": report.jobs_fetched,
              "new": report.jobs_new, "embedded": len(pending), "retired": retired,
              "status": report.status}
    logger.info("batch_complete", **result)
    return result
