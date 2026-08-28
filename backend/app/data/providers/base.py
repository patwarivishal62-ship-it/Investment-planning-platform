"""Provider abstraction. Nothing outside this package talks to a vendor."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

__all__ = ["MarketDataProvider", "MarketDataStatus", "DataProviderError", "Asset", "HistoricalPrice", "MarketPrice"]


class DataProviderError(Exception):
    """Raised when a provider cannot supply data. Never swallowed silently."""

    def __init__(self, message: str, cached_available: bool = False, cached_at: str | None = None):
        super().__init__(message)
        self.cached_available = cached_available
        self.cached_at = cached_at


@dataclass
class Asset:
    symbol: str
    name: str
    assetClass: str
    country: str
    sector: str
    currency: str
    dataSource: str
    liquidity: float = 0.5

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "assetClass": self.assetClass,
            "country": self.country,
            "sector": self.sector,
            "currency": self.currency,
            "dataSource": self.dataSource,
            "liquidity": self.liquidity,
        }


@dataclass
class HistoricalPrice:
    date: str
    close: float
    adjusted: float | None = None
    volume: float | None = None


@dataclass
class MarketPrice:
    symbol: str
    price: float
    currency: str
    asOf: str
    changePct: float | None = None


@dataclass
class MarketDataStatus:
    mode: str                      # "demo" | "live" | "cached"
    provider: str
    lastUpdated: str
    assetCount: int = 0
    historyStart: str | None = None
    historyEnd: str | None = None
    warnings: list[str] = field(default_factory=list)
    quality: dict | None = None

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "lastUpdated": self.lastUpdated,
            "assetCount": self.assetCount,
            "historyStart": self.historyStart,
            "historyEnd": self.historyEnd,
            "warnings": self.warnings,
            "quality": self.quality,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MarketDataProvider(ABC):
    """Replaceable source of asset metadata and historical prices."""

    name: str = "base"
    mode: str = "demo"

    @abstractmethod
    async def get_assets(self) -> list[Asset]: ...

    @abstractmethod
    async def get_historical_prices(self, symbol: str, start, end) -> list[HistoricalPrice]: ...

    @abstractmethod
    async def get_latest_price(self, symbol: str) -> MarketPrice: ...

    @abstractmethod
    async def get_price_matrix(self, symbols: list[str], start, end) -> pd.DataFrame: ...

    @abstractmethod
    def status(self) -> MarketDataStatus: ...
