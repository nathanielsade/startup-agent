from fastapi import Depends

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.ports.repository import JobRepository

from api.auth import get_current_user
from api.deps import get_settings

# Lazy module singletons for the Postgres connections (avoid reconnecting per request).
_pg_jobs = None
_pg_users = None


def _pg(database_url: str):
    global _pg_jobs, _pg_users
    if _pg_jobs is None:
        from startup_agent.adapters.storage.postgres_repository import PostgresJobRepository
        from startup_agent.adapters.storage.postgres_user_repository import PostgresUserRepository
        _pg_jobs = PostgresJobRepository(database_url)
        _pg_jobs.init_schema()
        _pg_users = PostgresUserRepository(database_url)
    return _pg_jobs, _pg_users


def get_scoped_repo(user_id: str = Depends(get_current_user),
                    settings=Depends(get_settings)) -> JobRepository:
    """Per-user repository for the current request.

    Cloud (DATABASE_URL set) → a UserScopedRepository over shared Postgres jobs with
    this user's CV/prefs/profile. Local/dev (no DATABASE_URL) → the single-tenant
    SQLite repo, unchanged.
    """
    if settings.database_url:
        from startup_agent.adapters.storage.user_scoped import UserScopedRepository
        jobs, users = _pg(settings.database_url)
        return UserScopedRepository(jobs, users, user_id)
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    return repo


def get_user_ctx(user_id: str = Depends(get_current_user), settings=Depends(get_settings)):
    """(user_repo, user_id) in cloud mode, or None locally (no per-user store)."""
    if not settings.database_url:
        return None
    _, users = _pg(settings.database_url)
    return (users, user_id)
