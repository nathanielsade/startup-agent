import typer

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository

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


if __name__ == "__main__":
    app()
