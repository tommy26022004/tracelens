from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FYP — Agentic SME Loan Analysis"
    app_version: str = "0.1.0"
    environment: str = "development"

    cors_origins: list[str] = ["http://localhost:5173"]

    # Persistence
    database_url: str = "postgresql+psycopg://fyp:fyp@localhost:5432/fyp"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    # LLM — provider-agnostic, default Gemini free tier
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Auth
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 30


settings = Settings()
