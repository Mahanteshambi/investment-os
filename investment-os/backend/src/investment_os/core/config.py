"""Application configuration via Pydantic v2 BaseSettings.

Reads from environment variables and a .env file in the backend root.
All other modules should import `settings` from here — never read os.environ directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve backend root regardless of where the process is started from
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # .../investment-os/backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Kite / Zerodha ──────────────────────────────────────────────────────
    kite_api_key: str = Field(default="", alias="KITE_API_KEY")
    kite_api_secret: str = Field(default="", alias="KITE_API_SECRET")
    kite_access_token: str = Field(default="", alias="KITE_ACCESS_TOKEN")

    # ── Google Sheets ────────────────────────────────────────────────────────
    google_sheets_credentials_json: Path = Field(
        default=_BACKEND_ROOT / "credentials" / "google_service_account.json",
        alias="GOOGLE_SHEETS_CREDENTIALS_JSON",
    )
    google_sheet_id: str = Field(default="", alias="GOOGLE_SHEET_ID")

    # ── Database ─────────────────────────────────────────────────────────────
    database_path: Path = Field(
        default=_BACKEND_ROOT / "data" / "investment_os.duckdb",
        alias="DATABASE_PATH",
    )

    # Token cache written after exchange_token() so token survives restarts
    kite_token_cache_path: Path = Field(
        default=_BACKEND_ROOT / "data" / "kite_token.json",
        alias="KITE_TOKEN_CACHE_PATH",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    environment: Literal["development", "production", "test"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )

    @field_validator("database_path", "google_sheets_credentials_json", "kite_token_cache_path", mode="before")
    @classmethod
    def _resolve_path(cls, v: str | Path) -> Path:
        p = Path(v)
        # Relative paths anchored to backend root
        return p if p.is_absolute() else (_BACKEND_ROOT / p).resolve()

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def log_level(self) -> str:
        return "INFO" if self.is_production else "DEBUG"


# Module-level singleton — import this everywhere
settings = Settings()
