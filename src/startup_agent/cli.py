from collections import Counter

import typer

from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.companies.loader import load_companies_from_seed
from startup_agent.config.preferences_loader import load_preferences
from startup_agent.config.settings import Settings
from startup_agent.cv.loader import read_pdf_text
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.services.health_check import CompanyHealthChecker
from startup_agent.services.ingestion import IngestionService
app = typer.Typer(help="Israeli startup job agent")


@app.command("init-db")
def init_db(db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Create the SQLite schema."""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    typer.echo(f"Database initialized at {db_path}")


@app.command("version")
def version() -> None:
    typer.echo("startup-agent 0.1.0")


@app.command("refresh-companies")
def refresh_companies(
    db_path: str = typer.Option("jobs.db", "--db-path"),
    seed: str = typer.Option("data/companies.json", "--seed"),
) -> None:
    """Load the company seed file into the database."""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    companies = load_companies_from_seed(seed)
    for company in companies:
        repo.upsert_company(company)
    typer.echo(f"Loaded {len(companies)} companies into {db_path}")


@app.command("run")
def run(db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Fetch new jobs from all companies into the database."""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    service = IngestionService(repo=repo, factory=ATSAdapterFactory())
    report = service.run()
    typer.echo(
        f"companies={report.companies_count} fetched={report.jobs_fetched} "
        f"new={report.jobs_new} status={report.status}"
    )


@app.command("match")
def match(db_path: str = typer.Option("jobs.db", "--db-path"),
          llm: bool = typer.Option(False, "--llm", help="Also score candidates with Claude")) -> None:
    """Rank stored jobs against the CV. --llm adds Claude scoring + reasons."""
    settings = Settings()
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    prefs = load_preferences(settings.preferences_path)
    embedder = LocalEmbedder(settings.embedding_model)
    names = {c.id_hash: c.name for c in repo.get_companies()}

    if llm:
        from startup_agent.adapters.ranking.claude_ranker import ClaudeRanker
        from startup_agent.services.hybrid_matching import HybridMatchingService

        ranker = ClaudeRanker(api_key=settings.anthropic_api_key, model=settings.llm_model)
        service = HybridMatchingService(
            repo=repo, embedder=embedder, ranker=ranker, preferences=prefs,
            sim_threshold=settings.match_threshold, llm_threshold=settings.llm_threshold,
        )
        results = service.run()
        typer.echo(f"{len(results)} matching jobs (LLM score >= {settings.llm_threshold}):")
        for job, m in results:
            typer.echo(f"  [{m.score}] {job.title} @ {names.get(job.company_id, '?')} "
                       f"— {job.location or 'n/a'} — {m.reason} — {job.url}")
        return

    from startup_agent.services.matching import SimilarityMatchingService
    service = SimilarityMatchingService(repo=repo, embedder=embedder,
                                        preferences=prefs, threshold=settings.match_threshold)
    results = service.run()
    typer.echo(f"{len(results)} matching jobs (similarity >= {settings.match_threshold}):")
    for job, score in results:
        typer.echo(f"  [{score:.2f}] {job.title} @ {names.get(job.company_id, '?')} "
                   f"— {job.location or 'n/a'} — {job.url}")


@app.command("load-cv")
def load_cv(path: str = typer.Option(..., "--path"),
            db_path: str = typer.Option("jobs.db", "--db-path")) -> None:
    """Parse a CV PDF, embed it locally, and store it."""
    settings = Settings()
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    text = read_pdf_text(path)
    embedder = LocalEmbedder(settings.embedding_model)
    vector = embedder.embed([text])[0]
    repo.save_cv(path=path, text=text, embedding=to_bytes(vector), model=settings.embedding_model)
    typer.echo(f"Loaded CV ({len(text)} chars) and stored its embedding.")


@app.command("check-companies")
def check_companies(
    db_path: str = typer.Option("jobs.db", "--db-path"),
    show: str = typer.Option(
        "failed,empty", "--show",
        help="comma list of statuses to list (ok,empty,failed,unsupported)",
    ),
) -> None:
    """Health-check every company: can we actually fetch jobs from it?"""
    repo = SQLiteJobRepository(db_path)
    repo.init_schema()
    results = CompanyHealthChecker(repo, ATSAdapterFactory()).check()
    counts = Counter(r.status for r in results)
    typer.echo(
        f"total={len(results)}  ok={counts['ok']}  empty={counts['empty']}  "
        f"failed={counts['failed']}  unsupported={counts['unsupported']}"
    )
    wanted = {s.strip() for s in show.split(",") if s.strip()}
    for r in sorted(results, key=lambda r: (r.status, r.name)):
        if r.status in wanted:
            line = f"  [{r.status}] {r.name} ({r.ats_type})"
            if r.status == "ok":
                line += f" — {r.job_count} jobs"
            if r.error:
                line += f" — {r.error}"
            typer.echo(line)


if __name__ == "__main__":
    app()
