"""GFI Platform - Application Configuration."""
import os
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "GFI Agentic AI Platform"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "CHANGE-ME-in-production-use-a-real-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENVIRONMENT: str = "development"  # development | staging | production

    # Database — PostgreSQL obligatoire en production
    DATABASE_URL: str = "sqlite+aiosqlite:///./gfi_dev.db"
    DATABASE_URL_SYNC: str = "sqlite:///./gfi_dev.db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # MFA
    MFA_ISSUER: str = "GFI Platform"
    MFA_ENFORCE: bool = False  # set True to make MFA mandatory

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        env = os.getenv("ENVIRONMENT", "development")
        if env in ("production", "staging") and "sqlite" in v.lower():
            raise ValueError(
                "SQLite is forbidden in production/staging. "
                "Set DATABASE_URL to a PostgreSQL connection string: "
                "postgresql+asyncpg://user:pass@host:5432/dbname"
            )
        return v

    # Object Storage (S3/MinIO)
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_DOCUMENTS: str = "gfi-documents"
    S3_BUCKET_RENDERS: str = "gfi-renders"
    S3_BUCKET_ARTIFACTS: str = "gfi-artifacts"
    S3_USE_SSL: bool = False

    # OCR
    OCR_ENGINE: str = "paddleocr"  # paddleocr | tesseract | easyocr
    OCR_DEFAULT_LANGS: str = "fr,en"
    OCR_DPI: int = 300
    OCR_CONFIDENCE_THRESHOLD: float = 0.6

    # AI / LLM (OpenRouter — OpenAI-compatible)
    LLM_PROVIDER: str = "openai"  # openai-compatible via OpenRouter
    LLM_MODEL: str = "openai/gpt-5.4"
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://openrouter.ai/api/v1"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4096

    # Google Drive Integration (per-user OAuth2)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/import?oauth_callback=google"

    # Redis (optional job queue)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rendering
    RENDER_DPI: int = 300
    RENDER_FORMAT: str = "png"

    # Policies
    VAT_RATES_ALLOWED: str = "0,7,10,14,20"
    ROUNDING_TOLERANCE: float = 0.02
    CONFIDENCE_GATE_THRESHOLD: float = 0.7
    MAX_RESOLUTION_ATTEMPTS: int = 3

    # File limits
    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: str = "pdf,png,jpg,jpeg,tiff,xlsx,csv"

    # ── GFI v7.0 Fiscal Constants ──
    TVA_TAUX: float = 0.19
    IBS_TAUX_PME: float = 0.19       # IBS taux PME (CA < seuil)
    IBS_TAUX_AUTRE: float = 0.26     # IBS taux autres entreprises
    TAP_TAUX_DEFAULT: float = 0.02
    CNAS_PATRONAL: float = 0.26
    CNAS_SALARIAL: float = 0.09
    CASNOS_TAUX: float = 0.12
    TIMBRE_CFF_DEFAUT: int = 15000   # Timbre CFF en DA (AID §13.1)
    LIBERATION_RATIO: float = 0.50
    CLOTURE_HEURE: int = 2  # hour of day (02:00) for monthly closing
    META_AUTO_DEPLOY: bool = False  # INVARIANT: never auto-deploy generated code
    META_SCORE_CONFIANCE_MIN: int = 80  # minimum AI confidence to process

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()
