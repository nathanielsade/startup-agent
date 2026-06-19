from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.config.settings import Settings
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.repository import JobRepository


def get_settings() -> Settings:
    return Settings()


def get_repo() -> JobRepository:
    repo = SQLiteJobRepository(get_settings().db_path)
    repo.init_schema()
    return repo


def get_embedder() -> Embedder:
    return LocalEmbedder(get_settings().embedding_model)


def get_factory() -> ATSAdapterFactory:
    return ATSAdapterFactory()
