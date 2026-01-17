"""Application configuration from environment variables."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Annotation Service"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/annotation_db"
    )

    # Redis (for Celery)
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_base_path: str = Field(default="./storage")
    s3_bucket_name: str | None = None
    s3_region: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Google Cloud Vision OCR
    google_cloud_credentials_path: str | None = None
    ocr_provider: Literal["google_vision", "mock"] = "google_vision"

    # Evaluation thresholds
    correct_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    partial_threshold: float = Field(default=0.50, ge=0.0, le=1.0)

    # Sentence Transformer model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    @field_validator("partial_threshold")
    @classmethod
    def partial_must_be_less_than_correct(cls, v, info):
        correct = info.data.get("correct_threshold", 0.75)
        if v >= correct:
            raise ValueError("partial_threshold must be less than correct_threshold")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
