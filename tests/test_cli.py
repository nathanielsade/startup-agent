from typer.testing import CliRunner

from startup_agent.cli import app

runner = CliRunner()


def test_init_db_creates_schema(tmp_path):
    db = tmp_path / "t.db"
    result = runner.invoke(app, ["init-db", "--db-path", str(db)])
    assert result.exit_code == 0
    assert db.exists()
    assert "initialized" in result.stdout.lower()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
