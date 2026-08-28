"""Real provider: a thin, replaceable REST adapter.

Contract expected from MARKET_DATA_BASE_URL (documented in docs/DATA_PROVIDERS.md):

    GET  {base}/assets
         -> [{"symbol","name","assetClass","country","sector","currency","liquidity"}]

    GET  {base}/history?symbol=XYZ&start=YYYY-MM-DD&end=YYYY-MM-DD
         -> [{"date":"YYYY-MM-DD","close":123.4,"adjusted":123.4,"volume":...}]

    GET  {base}/quote?symbol=XYZ
         -> {"symbol","price","currency","asOf","changePct"}

If the API key or base URL is missing, or the request fails, this raises
DataProviderError. It NEVER invents numbers: the caller decides whether to fall
back to cached data or to demo mode, and must label whichever it uses.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path

import httpx
import pandas as pd

from .base import (
    Asset,
    DataProviderError,
    HistoricalPrice,
    MarketDataProvider,
    MarketDataStatus,
    MarketPrice,
    utc_now_iso,
)

__all__ = ["RealMarketDataProvider"]


class RealMarketDataProvider(MarketDataProvider):
    name = "RealMarketDataProvider"
    mode = "live"

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 15.0,
        cache_dir: str | None = None,
    ):
        if not base_url:
            raise DataProviderError(
                "MARKET_DATA_BASE_URL is not configured. Set it in .env or switch "
                "MARKET_DATA_PROVIDER=demo."
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.cache_dir = Path(cache_dir or ".cache/marketdata")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_failure: str | None = None
        self._cached_mode = False

    # ------------------------------------------------------------- internals
    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _cache_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, key: str):
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return payload

    def _write_cache(self, key: str, payload) -> None:
        try:
            self._cache_path(key).write_text(json.dumps(payload, default=str))
        except OSError:  # pragma: no cover - cache is best effort
            pass

    async def _get(self, path: str, params: dict | None = None, cache_key: str | None = None):
        if cache_key:
            key = cache_key
        elif params:
            key = f"{path}?{json.dumps(params, sort_keys=True, default=str)}"
        else:
            key = path
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=self._headers())
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            cached = self._read_cache(key)
            if cached is not None:
                self._cached_mode = True
                self._last_failure = f"{type(exc).__name__}: {exc}"
                return cached, True
            raise DataProviderError(
                f"Market data provider request failed ({type(exc).__name__}). "
                "Market data is temporarily unavailable."
            ) from exc
        self._write_cache(key, payload)
        self._cached_mode = False
        return payload, False

    # ------------------------------------------------------------------- api
    async def get_assets(self) -> list[Asset]:
        payload, _ = await self._get("/assets", cache_key="/assets")
        if not isinstance(payload, list):
            raise DataProviderError("Provider returned an unexpected /assets payload")
        assets = []
        for row in payload:
            try:
                assets.append(
                    Asset(
                        symbol=str(row["symbol"]),
                        name=str(row.get("name", row["symbol"])),
                        assetClass=str(row.get("assetClass", "other")),
                        country=str(row.get("country", "IN")),
                        sector=str(row.get("sector", "Unknown")),
                        currency=str(row.get("currency", "INR")),
                        dataSource=self.name,
                        liquidity=float(row.get("liquidity", 0.5)),
                    )
                )
            except (KeyError, TypeError) as exc:
                raise DataProviderError(f"Malformed asset record from provider: {row!r}") from exc
        return assets

    async def get_historical_prices(self, symbol: str, start, end) -> list[HistoricalPrice]:
        params = {"symbol": symbol, "start": str(start)[:10], "end": str(end)[:10]}
        payload, _ = await self._get("/history", params=params)
        if not isinstance(payload, list):
            raise DataProviderError(f"Provider returned an unexpected /history payload for {symbol}")
        return [
            HistoricalPrice(
                date=str(row["date"])[:10],
                close=float(row["close"]),
                adjusted=(float(row["adjusted"]) if row.get("adjusted") is not None else None),
                volume=(float(row["volume"]) if row.get("volume") is not None else None),
            )
            for row in payload
            if row.get("date") is not None and row.get("close") is not None
        ]

    async def get_latest_price(self, symbol: str) -> MarketPrice:
        payload, _ = await self._get("/quote", params={"symbol": symbol}, cache_key=f"/quote?{symbol}")
        return MarketPrice(
            symbol=str(payload.get("symbol", symbol)),
            price=float(payload["price"]),
            currency=str(payload.get("currency", "INR")),
            asOf=str(payload.get("asOf", utc_now_iso())),
            changePct=(float(payload["changePct"]) if payload.get("changePct") is not None else None),
        )

    async def get_price_matrix(self, symbols, start, end) -> pd.DataFrame:
        """Fetch each symbol and align on the union of dates.

        Missing observations are left as NaN on purpose -- the quality engine
        reports them instead of the pipeline silently filling them in.
        """
        frames = {}
        for symbol in symbols:
            rows = await self.get_historical_prices(symbol, start, end)
            if not rows:
                frames[symbol] = pd.Series(dtype=float, name=symbol)
                continue
            series = pd.Series(
                [r.adjusted if r.adjusted is not None else r.close for r in rows],
                index=pd.DatetimeIndex([pd.Timestamp(r.date) for r in rows]),
                name=symbol,
            )
            frames[symbol] = series[~series.index.duplicated(keep="last")].sort_index()
        matrix = pd.DataFrame(frames)
        if not matrix.empty:
            matrix = matrix.sort_index()
            matrix.index.name = "date"
        return matrix

    def status(self) -> MarketDataStatus:
        mode = "cached" if self._cached_mode else "live"
        warnings = []
        if self._cached_mode:
            warnings.append(
                "Market data is temporarily unavailable. Showing cached data"
                + (f" from {self._last_failure}." if self._last_failure else ".")
            )
        if not self.api_key:
            warnings.append("Provider is configured without an API key; access may be rate limited.")
        return MarketDataStatus(
            mode=mode,
            provider=self.name,
            lastUpdated=utc_now_iso(),
            warnings=warnings,
        )
