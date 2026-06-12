import pytest

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository


@pytest.fixture
def repo():
    r = SQLiteJobRepository(":memory:")
    r.init_schema()
    return r
