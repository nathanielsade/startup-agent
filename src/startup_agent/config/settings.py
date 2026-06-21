from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "jobs.db"
    cv_path: str = ""
    embedding_provider: str = "local"     # "local" (sentence-transformers) | "openai"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_embedding_model: str = "text-embedding-3-small"
    shortlist_size: int = 20
    anthropic_api_key: str = ""
    digest_dir: str = "digests"
    match_threshold: float = 0.30
    preferences_path: str = "data/preferences.yaml"
    llm_model: str = "claude-opus-4-8"
    llm_threshold: int = 70
    llm_provider: str = "anthropic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = ""
    llm_recent_hours: int = 24
    # cloud (Phase 1)
    database_url: str = ""              # Postgres DSN (Supabase / local docker)
    supabase_jwt_secret: str = ""       # verifies Supabase auth JWTs (HS256)
    supabase_url: str = ""
    llm_daily_cap: int = 30             # per-user LLM calls/day
    cors_origins: str = ""              # comma-separated extra allowed origins (deploy)

    @property
    def active_embedding_model(self) -> str:
        """Model name stored alongside each vector — also the re-embed key."""
        if self.embedding_provider == "openai":
            return self.openai_embedding_model
        return self.embedding_model
