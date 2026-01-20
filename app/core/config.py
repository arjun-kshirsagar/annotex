"""Application configuration from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # =========================================================================
    # Application
    # =========================================================================
    app_name: str = "Annotex"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # =========================================================================
    # API
    # =========================================================================
    api_v1_prefix: str = "/api/v1"

    # =========================================================================
    # Database (PostgreSQL)
    # =========================================================================
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/annotation_db"
    )

    # =========================================================================
    # Redis (Celery Queue)
    # =========================================================================
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")
    celery_task_always_eager: bool = Field(default=False)

    # =========================================================================
    # File Storage
    # =========================================================================
    storage_backend: Literal["local", "s3"] = "local"
    storage_base_path: str = Field(default="./storage")

    # S3 Storage (optional)
    s3_bucket_name: str | None = None
    s3_region: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # =========================================================================
    # Google Cloud Vision OCR
    # =========================================================================
    # Provider: 'mock' for testing, 'google_vision' for production
    ocr_provider: Literal["google_vision", "mock"] = "mock"

    # Option 1: Path to service account JSON file
    google_cloud_credentials_path: str | None = None

    # Option 2: Standard Google Cloud SDK environment variable
    google_application_credentials: str | None = None

    # Option 3: Base64 encoded service account key (for containerized deployments)
    google_service_account_key_base64: str | None = None

    # =========================================================================
    # Evaluation Configuration
    # =========================================================================
    # Thresholds for verdict determination
    # correct: >= correct_threshold (default 0.75)
    # partial: >= partial_threshold and < correct_threshold (default 0.50-0.75)
    # incorrect: < partial_threshold (default < 0.50)
    correct_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    partial_threshold: float = Field(default=0.50, ge=0.0, le=1.0)

    # Sentence Transformer model for semantic similarity
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # =========================================================================
    # Logging
    # =========================================================================
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    @field_validator("partial_threshold")
    @classmethod
    def partial_must_be_less_than_correct(cls, v, info):
        correct = info.data.get("correct_threshold", 0.75)
        if v >= correct:
            raise ValueError("partial_threshold must be less than correct_threshold")
        return v

    def get_google_credentials_path(self) -> str | None:
        """Get the effective Google credentials path.

        Priority:
        1. google_cloud_credentials_path (explicit config)
        2. google_application_credentials (standard env var)

        Note: base64 key is handled separately in ocr_service.

        Returns:
            Path to credentials file or None
        """
        return self.google_cloud_credentials_path or self.google_application_credentials

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
