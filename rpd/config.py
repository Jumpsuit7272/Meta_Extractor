"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RPD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Storage
    upload_dir: Path = Path("uploads")
    result_dir: Path = Path("results")
    max_upload_mb: int = 1024

    # Extraction
    default_extractor: str = "builtin"
    ocr_enabled: bool = True
    tesseract_path: str | None = None
    geolocation_lookup_enabled: bool = True  # Reverse geocode GPS from images

    # Comparison
    default_similarity_threshold: float = 0.95
    normalize_dates: bool = True
    normalize_currency: bool = True

    # Storage backend (local | s3)
    storage_backend: str = "local"
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"

    # Async (Celery/Redis)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"


settings = Settings()
