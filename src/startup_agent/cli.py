from collections import Counter
from datetime import date

import typer

from startup_agent.adapters.delivery.file_channel import FileChannel
from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.companies.loader import load_companies_from_seed
from startup_agent.config.preferences_loader import load_preferences
from startup_agent.config.settings import Settings
from startup_agent.cv.loader import read_pdf_text
from startup_agent.digest.renderer import render_markdown
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.services.digest import DigestService
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


@app.command("health-report")
def health_report(
    out: str = typer.Option("docs/integration-status.md", "--out"),
    database_url: str = typer.Option("", "--database-url"),
) -> None:
    """Probe every company live and write a Markdown integration-status report."""
    from datetime import datetime, timezone
    from pathlib import Path

    from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
    from startup_agent.services.health_report import render_health_report

    dsn = database_url or Settings().database_url
    if not dsn:
        typer.echo("No DATABASE_URL configured (set it or pass --database-url)")
        raise typer.Exit(1)
    repo = PostgresJobRepository(dsn)
    repo.init_schema()
    results = CompanyHealthChecker(repo, ATSAdapterFactory()).check()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(render_health_report(results, generated))
    typer.echo(f"wrote {out}: {dict(Counter(r.status for r in results))}")


@app.command("digest")
def digest(db_path: str = typer.Option("jobs.db", "--db-path"),
           llm: bool = typer.Option(False, "--llm", help="Use Claude scoring + reasons")) -> None:
    """Build a digest of NEW matching jobs and write it to a dated markdown file."""
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
        results = HybridMatchingService(
            repo=repo, embedder=embedder, ranker=ranker, preferences=prefs,
            sim_threshold=settings.match_threshold, llm_threshold=settings.llm_threshold,
        ).run()
        entries = [(job, m.score, m.reason) for job, m in results]
    else:
        from startup_agent.services.matching import SimilarityMatchingService
        results = SimilarityMatchingService(
            repo=repo, embedder=embedder, preferences=prefs, threshold=settings.match_threshold
        ).run()
        entries = [(job, int(score * 100), None) for job, score in results]

    channel = FileChannel(settings.digest_dir)
    title = date.today().isoformat()
    fresh = DigestService(repo, channel, render_markdown).run(title, entries, names)
    if fresh:
        typer.echo(f"{len(fresh)} new jobs -> {channel.path_for(title)}")
    else:
        typer.echo("0 new jobs — no digest written")


@app.command("batch")
def batch(seed: str = typer.Option("data/companies.json", "--seed"),
          database_url: str = typer.Option("", "--database-url")) -> None:
    """Cloud batch: load companies, fetch all jobs, embed new ones, retire vanished
    jobs — writing to Postgres. Run on a schedule (GitHub Actions)."""
    settings = Settings()
    dsn = database_url or settings.database_url
    if not dsn:
        typer.echo("No DATABASE_URL configured (set it or pass --database-url)")
        raise typer.Exit(1)
    from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
    from startup_agent.companies.batch import run_batch
    from startup_agent.factories.embedder_factory import build_embedder
    repo = PostgresJobRepository(dsn)
    repo.init_schema()
    embedder = build_embedder(settings)
    from startup_agent.adapters.summarizing.openai_summarizer import OpenAIJobSummarizer
    summarizer = OpenAIJobSummarizer(api_key=settings.openai_api_key,
                                     model=settings.llm_rerank_model,
                                     base_url=settings.openai_base_url)
    result = run_batch(repo, ATSAdapterFactory(), embedder,
                       model=settings.active_embedding_model, seed_path=seed,
                       summarizer=summarizer)
    typer.echo(f"batch done: {result}")


if __name__ == "__main__":
    app()
