from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://sca_user:changeme@localhost:5432/sales_call_analyzer"
    database_url_sync: str = "postgresql+psycopg2://sca_user:changeme@localhost:5432/sales_call_analyzer"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket_recordings: str = "call-recordings"
    minio_bucket_processed: str = "call-processed"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "insecure-dev-secret-replace-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440
    jwt_refresh_token_expire_days: int = 7

    # OpenSearch
    opensearch_url: str = "http://localhost:9200"

    # LanguageTool
    languagetool_url: str = "http://localhost:8010"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2:3b"
    ollama_timeout_seconds: int = 900

    # Claude API (optional — enables high-accuracy LLM scoring when key is set)
    claude_api_key: str = ""
    claude_model: str = "claude-haiku-4-5-20251001"

    # ML Service
    ml_service_url: str = "http://localhost:8001"

    # App
    environment: str = "development"
    log_level: str = "INFO"
    max_upload_size_mb: int = 500
    allowed_audio_extensions: str = ".wav,.mp3,.m4a,.mp4,.ogg,.flac"
    allowed_origins: str = "http://localhost:5173,http://localhost"

    # Seed credentials
    seed_admin_email: str = "admin@company.com"
    seed_admin_password: str = "Admin@1234"
    seed_manager_email: str = "manager@company.com"
    seed_manager_password: str = "Manager@1234"
    seed_agent_email: str = "agent@company.com"
    seed_agent_password: str = "Agent@1234"

    @property
    def allowed_extensions_set(self) -> set[str]:
        return set(self.allowed_audio_extensions.split(","))

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
