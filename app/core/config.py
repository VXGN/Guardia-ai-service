from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # guardia_ai_service/


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    CORS_ORIGINS: list[str] = ["*"]
    DBSCAN_EPS_KM: float = 0.3
    DBSCAN_MIN_SAMPLES: int = 3
    RISK_DECAY_DAYS: int = 30
    NEWS_SCRAPE_MAX_ARTICLES_PER_SOURCE: int = 20
    NEWS_SCRAPE_MAX_PAGES: int = 3
    NEWS_SCRAPE_INCLUDE_SOURCES: str = "detik,kompas,insidelombok,postlombok"
    ENABLE_BACKGROUND_SYNC: bool = True
    NEWS_SYNC_INTERVAL_SECONDS: int = 900
    ANALYSIS_SYNC_INTERVAL_SECONDS: int = 300
    RUN_SYNC_ON_STARTUP: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        normalized = value.strip().replace("\r", "").replace("\n", "")
        if (normalized.startswith('"') and normalized.endswith('"')) or (
            normalized.startswith("'") and normalized.endswith("'")
        ):
            normalized = normalized[1:-1].strip()

        return normalized

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
