"""Asset-level statistical analytics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from fastapi import APIRouter

from ...analytics import advanced as adv
from ...analytics import correlation as corr
from ...analytics import risk as riskmod
from ...analytics import statistics as stats
from ...core.config import get_settings
from ...data.universe import by_symbol
from ...schemas.requests import AssetAnalyticsRequest, CorrelationRequest
from ...services.market_data import MarketDataService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/assets")
async def asset_analytics(request: AssetAnalyticsRequest) -> dict:
    """Per-asset descriptive statistics, risk metrics and distributions."""
    service = MarketDataService()
    snapshot = await service.get_snapshot(request.symbols, request.start, request.end)
    rf = request.riskFreeRate if request.riskFreeRate is not None else get_settings().risk_free_rate

    rows = []
    for symbol in snapshot.symbols:
        series = snapshot.returns[symbol].to_numpy(dtype=float)
        metrics = riskmod.risk_metrics_summary(series, snapshot.periods_per_year, rf)
        meta = by_symbol(symbol)
        rows.append(
            {
                "symbol": symbol,
                "name": meta.name,
                "assetClass": meta.assetClass,
                "sector": meta.sector,
                "country": meta.country,
                "currency": meta.currency,
                "liquidity": meta.liquidity,
                "price": float(snapshot.prices[symbol].iloc[-1]),
                "asOf": str(snapshot.prices[symbol].index[-1].date()),
                "historyStart": str(snapshot.prices[symbol].index[0].date()),
                "historyEnd": str(snapshot.prices[symbol].index[-1].date()),
                "observations": int(len(series)),
                **metrics,
                "descriptive": stats.describe(series),
            }
        )

    correlation = corr.pearson_correlation_matrix(snapshot.returns)
    return {
        "assets": rows,
        "symbols": snapshot.symbols,
        "correlation": {
            "symbols": list(correlation.columns),
            "matrix": [[None if not np.isfinite(v) else float(v) for v in row]
                       for row in correlation.to_numpy(dtype=float)],
            "averagePairwiseCorrelation": corr.average_pairwise_correlation(correlation),
        },
        "pca": adv.principal_components(snapshot.returns),
        "period": {"start": snapshot.start, "end": snapshot.end},
        "dataQuality": {
            "score": round(snapshot.quality.score, 1),
            "grade": snapshot.quality.grade,
            "issues": [i.message for i in snapshot.quality.issues[:10]],
        },
    }


@router.post("/correlation")
async def correlation(request: CorrelationRequest) -> dict:
    service = MarketDataService()
    snapshot = await service.get_snapshot(request.symbols, request.start, request.end)
    frame = snapshot.returns
    if request.window:
        frame = frame.tail(int(request.window))
    matrix = corr.pearson_correlation_matrix(frame)
    payload = {
        "symbols": list(matrix.columns),
        "matrix": [[None if not np.isfinite(v) else float(v) for v in row]
                   for row in matrix.to_numpy(dtype=float)],
        "averagePairwiseCorrelation": corr.average_pairwise_correlation(matrix),
        "windowDays": int(len(frame)),
        "period": {"start": str(frame.index[0].date()), "end": str(frame.index[-1].date())},
    }
    if request.rollingSymbol and request.rollingSymbolB:
        rolled = corr.rolling_correlation(frame, request.rollingSymbol, request.rollingSymbolB,
                                          window=request.rollingWindow).dropna()
        payload["rolling"] = [
            {"date": str(pd.Timestamp(ts).date()), "value": float(v)} for ts, v in rolled.items()
        ]
    return payload
