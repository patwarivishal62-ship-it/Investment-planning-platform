"""Application configuration.

All financial assumptions are configurable and sourced from environment
variables (see .env.example). Nothing financial is hard-coded in the
analytics modules -- every module receives its assumptions as arguments.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Data provider -------------------------------------------------
    # "demo"  -> deterministic synthetic data (always available, clearly labelled)
    # "real"  -> live provider configured via MARKET_DATA_BASE_URL + API key
    market_data_provider: Literal["demo", "real"] = "demo"
    market_data_base_url: str = ""
    market_data_api_key: str = ""
    market_data_timeout_seconds: float = 15.0
    # Where the local cache of provider responses lives (never committed).
    market_data_cache_dir: str = ".cache/marketdata"

    # ---- Financial assumptions ----------------------------------------
    risk_free_rate: float = Field(default=0.065, ge=0.0, le=0.5)
    default_lookback_years: int = Field(default=10, ge=1, le=40)
    default_rebalance_frequency: str = "quarterly"
    trading_days_per_year: int = Field(default=252, ge=1, le=366)
    # MAR (minimum acceptable return) used by Sortino / downside deviation.
    default_mar: float = 0.0
    var_confidence: float = Field(default=0.95, gt=0.0, lt=1.0)
    # Transaction costs are assumptions, configurable per request too.
    default_transaction_cost_bps: float = Field(default=10.0, ge=0.0, le=1000.0)

    # ---- Engine limits -------------------------------------------------
    max_candidate_portfolios: int = Field(default=50_000, ge=100, le=500_000)
    default_candidate_portfolios: int = Field(default=25_000, ge=100, le=500_000)
    max_monte_carlo_paths: int = Field(default=50_000, ge=100, le=200_000)
    analytics_cache_size: int = Field(default=64, ge=1, le=1024)

    # ---- Runtime -------------------------------------------------------
    cors_origins: str = "*"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
