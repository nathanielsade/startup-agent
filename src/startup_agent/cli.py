import typer

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.companies.loader import load_companies_from_seed
from startup_agent.factories.ats_factory import ATSAdapterFactory
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


if __name__ == "__main__":
    app()
