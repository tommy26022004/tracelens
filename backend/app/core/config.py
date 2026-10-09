from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FYP — Agentic SME Loan Analysis"
    app_version: str = "0.1.0"
    environment: str = "development"
    source_documents_dir: Path = Path(__file__).resolve().parents[2] / "data" / "source_documents"

    cors_origins: list[str] = ["http://localhost:5173"]

    # Persistence
    database_url: str = "postgresql+psycopg://fyp:fyp@localhost:5432/fyp"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # LLM — provider-agnostic, default Gemini free tier
    llm_provider: str = "gemini"
    embeddings_provider: str = "local"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    rag_score_threshold: float = Field(default=0.12, ge=0, le=1)
    rag_results_per_query: int = Field(default=3, ge=1, le=5)
    rag_chunk_chars: int = Field(default=1800, ge=200, le=6000)
    rag_context_chars: int = Field(default=20000, ge=1000, le=60000)

    # Auth
    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 30


settings = Settings()
