"""Demo provider: deterministic synthetic data, always available, clearly labelled."""
from __future__ import annotations

import asyncio
from datetime import date, datetime

import pandas as pd

from ..synthetic import DemoDataWarning, DemoParams, generate_demo_prices
from ..universe import UNIVERSE
from .base import (
    Asset,
    DataProviderError,
    HistoricalPrice,
    MarketDataProvider,
    MarketDataStatus,
    MarketPrice,
    utc_now_iso,
)

__all__ = ["DemoMarketDataProvider"]


class DemoMarketDataProvider(MarketDataProvider):
    """Serves seeded synthetic series. Every response carries the DEMO label."""

    name = "DemoMarketDataProvider"
    mode = "demo"

    def __init__(self, seed: int = 20240501, start: str = "2015-01-01", end: str | None = None):
        self.params = DemoParams(seed=seed)
        self.start = start
        self.end = end or date.today().isoformat()
        self._matrix: pd.DataFrame | None = None
        self._generated_at: str = utc_now_iso()

    # ------------------------------------------------------------------ cache
    def matrix(self) -> pd.DataFrame:
        if self._matrix is None:
            self._matrix = generate_demo_prices(
                [a.symbol for a in UNIVERSE],
                start=self.start,
                end=self.end,
                params=self.params,
            )
            self._generated_at = utc_now_iso()
        return self._matrix

    # ------------------------------------------------------------------- api
    async def get_assets(self) -> list[Asset]:
        frame = await asyncio.to_thread(self.matrix)
        universe = []
        for meta in UNIVERSE:
            if meta.symbol not in frame.columns:
                continue
            universe.append(
                Asset(
                    symbol=meta.symbol,
                    name=meta.name,
                    assetClass=meta.assetClass,
                    country=meta.country,
                    sector=meta.sector,
                    currency=meta.currency,
                    dataSource=meta.dataSource,
                    liquidity=meta.liquidity,
                )
            )
        return universe

    async def get_historical_prices(self, symbol: str, start, end) -> list[HistoricalPrice]:
        frame = await asyncio.to_thread(self.matrix)
        if symbol not in frame.columns:
            raise DataProviderError(f"Unknown demo symbol: {symbol}")
        series = frame[symbol].loc[str(start) : str(end)].dropna()
        return [
            HistoricalPrice(date=str(ts.date()), close=float(value), adjusted=float(value))
            for ts, value in series.items()
        ]

    async def get_latest_price(self, symbol: str) -> MarketPrice:
        frame = await asyncio.to_thread(self.matrix)
        if symbol not in frame.columns:
            raise DataProviderError(f"Unknown demo symbol: {symbol}")
        series = frame[symbol].dropna()
        if series.empty:
            raise DataProviderError(f"No demo price available for {symbol}")
        previous = float(series.iloc[-2]) if len(series) > 1 else float(series.iloc[-1])
        last = float(series.iloc[-1])
        return MarketPrice(
            symbol=symbol,
            price=last,
            currency="INR",
            asOf=str(series.index[-1].date()),
            changePct=(last / previous - 1.0) if previous else None,
        )

    async def get_price_matrix(self, symbols, start, end) -> pd.DataFrame:
        frame = await asyncio.to_thread(self.matrix)
        unknown = [s for s in symbols if s not in frame.columns]
        if unknown:
            raise DataProviderError(f"Unknown demo symbols: {unknown}")
        return frame.loc[str(start) : str(end), list(symbols)].copy()

    def status(self) -> MarketDataStatus:
        frame = self._matrix
        return MarketDataStatus(
            mode="demo",
            provider=self.name,
            lastUpdated=self._generated_at,
            assetCount=len(UNIVERSE),
            historyStart=str(frame.index[0].date()) if frame is not None and not frame.empty else None,
            historyEnd=str(frame.index[-1].date()) if frame is not None and not frame.empty else None,
            warnings=[
                DemoDataWarning,
                "Synthetic series generated from a seeded factor model. Do not treat these "
                "numbers as real historical market data.",
            ],
        )
