"""Market data service: provider access, quality gating and matrix building.

Responsibilities
----------------
* own the provider instance (never exposed to the API layer directly);
* run the data-quality pipeline before any analytics;
* build the return / mean / covariance matrices the optimizers need;
* cache expensive matrix construction;
* always report mode (demo | live | cached), provider and timestamp.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from ..analytics import correlation as corr
from ..analytics import returns as ret
from ..analytics import risk as riskmod
from ..core.config import Settings, get_settings
from ..core.logging import get_logger, log_duration
from ..data.providers.base import DataProviderError, MarketDataProvider
from ..data.providers.registry import build_provider
from ..data.quality import QualityReport, assess_quality
from ..data.universe import UNIVERSE, by_symbol, class_map, liquidity_map, sector_map

logger = get_logger("services.market_data")


@dataclass
class MarketSnapshot:
    """Everything the analytics engine needs for one request."""

    prices: pd.DataFrame
    returns: pd.DataFrame
    mu: np.ndarray                 # annualised arithmetic expected returns
    cov: np.ndarray                # annualised covariance
    symbols: list[str]
    quality: QualityReport
    start: str
    end: str
    periods_per_year: int
    return_method: str = "simple"
    class_map: dict[str, str] = field(default_factory=dict)
    sector_map: dict[str, str] = field(default_factory=dict)
    liquidity_map: dict[str, float] = field(default_factory=dict)

    @property
    def annualized_vols(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.cov), 0.0, None))

    def correlation(self) -> pd.DataFrame:
        return corr.pearson_correlation_matrix(self.returns)


class MarketDataService:
    def __init__(self, provider: MarketDataProvider | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._provider = provider
        self._lock = asyncio.Lock()
        self._quality_cache: dict[str, QualityReport] = {}
        self._snapshot_cache: dict[str, MarketSnapshot] = {}

    @property
    def provider(self) -> MarketDataProvider:
        if self._provider is None:
            self._provider = build_provider(self.settings)
        return self._provider

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        status = self.provider.status()
        payload = status.as_dict()
        payload["isDemo"] = status.mode == "demo"
        payload["providerConfigured"] = bool(
            self.settings.market_data_provider == "real" and self.settings.market_data_base_url
        )
        return payload

    # ---------------------------------------------------------------- assets
    async def get_assets(self) -> list[dict]:
        """Asset universe enriched with computed statistics from real data."""
        assets = await self.provider.get_assets()
        symbols = [a.symbol for a in assets]
        snapshot = await self.get_snapshot(symbols)
        correlations = snapshot.correlation()

        enriched = []
        for asset in assets:
            if asset.symbol not in snapshot.symbols:
                enriched.append({**asset.as_dict(), "available": False, "historyDays": 0})
                continue
            prices = snapshot.prices[asset.symbol].dropna()
            series = snapshot.returns[asset.symbol].dropna()
            metrics = riskmod.risk_metrics_summary(
                series.to_numpy(dtype=float),
                snapshot.periods_per_year,
                risk_free_rate=self.settings.risk_free_rate,
            )
            others = [c for c in correlations.columns if c != asset.symbol]
            avg_corr = float(np.mean([correlations.loc[asset.symbol, o] for o in others])) if others else 0.0
            enriched.append(
                {
                    **asset.as_dict(),
                    "available": True,
                    "price": float(prices.iloc[-1]) if len(prices) else None,
                    "asOf": str(prices.index[-1].date()) if len(prices) else None,
                    "historyDays": int(len(prices)),
                    "historyStart": str(prices.index[0].date()) if len(prices) else None,
                    "historyEnd": str(prices.index[-1].date()) if len(prices) else None,
                    "annualizedReturn": metrics.get("annualizedReturn"),
                    "volatility": metrics.get("volatility"),
                    "sharpe": metrics.get("sharpe"),
                    "sortino": metrics.get("sortino"),
                    "maxDrawdown": metrics.get("maxDrawdown"),
                    "avgCorrelation": avg_corr,
                    "dataQuality": snapshot.quality.symbolScores.get(asset.symbol),
                    "currency": asset.currency,
                }
            )
        return enriched

    async def get_history(self, symbol: str, start: date | str, end: date | str) -> list[dict]:
        rows = await self.provider.get_historical_prices(symbol, start, end)
        return [
            {"date": r.date, "close": r.close, "adjusted": r.adjusted, "volume": r.volume}
            for r in rows
        ]

    # -------------------------------------------------------------- snapshot
    async def get_snapshot(
        self,
        symbols: list[str] | None = None,
        start: date | str | None = None,
        end: date | str | None = None,
        min_years: float = 3.0,
    ) -> MarketSnapshot:
        """Prices -> quality gate -> returns -> annualised mu / covariance."""
        settings = self.settings
        end = str(end or date.today())
        start = str(start or f"{int(end[:4]) - settings.default_lookback_years}{end[4:]}")
        if symbols is None:
            universe_symbols = [a.symbol for a in UNIVERSE]
        else:
            universe_symbols = list(symbols)

        cache_key = f"{','.join(sorted(universe_symbols))}|{start}|{end}|{min_years}"
        if cache_key in self._snapshot_cache:
            return self._snapshot_cache[cache_key]

        async with self._lock:
            if cache_key in self._snapshot_cache:
                return self._snapshot_cache[cache_key]
            with log_duration(logger, "build_snapshot", symbols=len(universe_symbols), start=start, end=end):
                prices = await self.provider.get_price_matrix(universe_symbols, start, end)
                if prices is None or prices.empty:
                    raise DataProviderError(
                        "No price data was returned for the requested symbols and date range."
                    )

                quality = assess_quality(
                    prices,
                    base_currency="INR",
                    currencies={by_symbol(s).currency for s in prices.columns}
                    and {s: by_symbol(s).currency if s in {a.symbol for a in UNIVERSE} else "INR" for s in prices.columns},
                    min_observations=int(min_years * settings.trading_days_per_year),
                )
                usable = [s for s in prices.columns if s in quality.usableSymbols]
                if not usable:
                    raise DataProviderError(
                        "No asset has sufficient, valid history for this analysis. "
                        + "; ".join(i.message for i in quality.issues[:3])
                    )
                dropped = [s for s in prices.columns if s not in usable]
                if dropped:
                    logger.info("quarantined assets: %s", dropped)

                prices = prices[usable].dropna(how="all")
                returns = ret.returns_frame(prices, method="simple").dropna(how="all")
                # Assets with any remaining NaN returns are dropped rather than
                # silently filled: the quality engine already reported the gaps.
                complete = [c for c in returns.columns if returns[c].notna().all()]
                if complete and len(complete) < len(returns.columns):
                    logger.info("dropped incomplete series: %s", sorted(set(returns.columns) - set(complete)))
                    returns = returns[complete]
                    prices = prices[complete]

                periods = settings.trading_days_per_year
                mu = (returns.mean() * periods).to_numpy(dtype=float)
                cov = (returns.cov() * periods).to_numpy(dtype=float)
                cov = corr.nearest_psd(cov)

                snapshot = MarketSnapshot(
                    prices=prices,
                    class_map={s: class_map().get(s, "other") for s in returns.columns},
                    sector_map={s: sector_map().get(s, "Unknown") for s in returns.columns},
                    liquidity_map={s: liquidity_map().get(s, 0.5) for s in returns.columns},
                    returns=returns,
                    mu=mu,
                    cov=cov,
                    symbols=list(returns.columns),
                    quality=quality,
                    start=str(prices.index[0].date()),
                    end=str(prices.index[-1].date()),
                    periods_per_year=periods,
                )
                self._snapshot_cache[cache_key] = snapshot
                return snapshot

    def class_of(self) -> dict[str, str]:
        return class_map()

    def sector_of(self) -> dict[str, str]:
        return sector_map()

    def liquidity_of(self) -> dict[str, float]:
        return liquidity_map()

    def metadata(self, symbol: str) -> dict:
        meta = by_symbol(symbol)
        return {
            "symbol": meta.symbol,
            "name": meta.name,
            "assetClass": meta.assetClass,
            "country": meta.country,
            "sector": meta.sector,
            "currency": meta.currency,
            "liquidity": meta.liquidity,
        }


@lru_cache
def get_market_data_service() -> MarketDataService:
    return MarketDataService()
