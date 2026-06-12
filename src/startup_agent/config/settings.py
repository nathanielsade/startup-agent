from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "jobs.db"
    cv_path: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    shortlist_size: int = 20
    anthropic_api_key: str = ""
    digest_dir: str = "digests"
