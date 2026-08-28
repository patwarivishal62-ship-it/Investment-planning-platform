"""Transparent 'Platform Risk Score' (0-100).

This is deliberately NOT presented as an industry-standard measure. It is a
documented composite of eight observable, historical inputs; the API returns
the full breakdown so the user can see exactly how the number was produced.
"""
from __future__ import annotations

import numpy as np

__all__ = ["platform_risk_score", "risk_band", "COMPONENT_WEIGHTS", "COMPONENT_BANDS"]

COMPONENT_WEIGHTS = {
    "volatility": 0.22,
    "maxDrawdown": 0.20,
    "downsideDeviation": 0.13,
    "valueAtRisk": 0.10,
    "equityExposure": 0.13,
    "concentration": 0.07,
    "assetClassConcentration": 0.08,
    "illiquidity": 0.07,
}

# The value at which a component reaches its maximum risk contribution.
COMPONENT_BANDS = {
    "volatility": 0.30,
    "maxDrawdown": 0.50,
    "downsideDeviation": 0.25,
    "valueAtRisk": 0.04,     # daily 95% VaR
    "equityExposure": 1.00,
    "concentration": 1.00,
    "assetClassConcentration": 1.00,
    "illiquidity": 1.00,
}

BANDS = [
    (20, "Very Low"),
    (40, "Low"),
    (60, "Moderate"),
    (80, "High"),
    (100, "Very High"),
]


def risk_band(score: float) -> str:
    if score is None or not np.isfinite(score):
        return "Unavailable"
    for upper, label in BANDS:
        if score <= upper:
            return label
    return "Very High"


def _clamp01(value: float | None) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return float(min(max(value, 0.0), 1.0))


def _hhi(values) -> float:
    v = np.asarray(values, dtype=float)
    v = v[v > 0]
    if v.size == 0:
        return 1.0
    total = float(v.sum())
    if total <= 0:
        return 1.0
    p = v / total
    return float(np.sum(p**2))


def _normalized_hhi(weights) -> float:
    w = np.asarray(weights, dtype=float)
    w = w[w > 1e-12]
    n = w.size
    if n <= 1:
        return 1.0
    hhi = _hhi(w)
    return float((hhi - 1.0 / n) / (1.0 - 1.0 / n))


def platform_risk_score(
    volatility: float | None,
    max_drawdown: float | None,
    downside_deviation: float | None,
    daily_var: float | None,
    weights,
    symbols: list[str],
    class_of: dict[str, str],
    liquidity: dict[str, float] | None = None,
) -> dict:
    """Composite 0-100 risk score with a full component breakdown."""
    w = np.asarray(weights, dtype=float)
    liquidity = liquidity or {}

    equity_exposure = float(sum(w[i] for i, s in enumerate(symbols) if class_of.get(s) == "equity"))
    class_exposure: dict[str, float] = {}
    for i, s in enumerate(symbols):
        class_exposure[class_of.get(s, "other")] = class_exposure.get(class_of.get(s, "other"), 0.0) + float(w[i])

    weighted_liquidity = 0.0
    if liquidity:
        total = float(w.sum()) or 1.0
        weighted_liquidity = float(sum(w[i] * float(liquidity.get(s, 0.5)) for i, s in enumerate(symbols)) / total)

    raw = {
        "volatility": _clamp01((volatility or 0.0) / COMPONENT_BANDS["volatility"]),
        "maxDrawdown": _clamp01(abs(max_drawdown or 0.0) / COMPONENT_BANDS["maxDrawdown"]),
        "downsideDeviation": _clamp01((downside_deviation or 0.0) / COMPONENT_BANDS["downsideDeviation"]),
        "valueAtRisk": _clamp01((daily_var or 0.0) / COMPONENT_BANDS["valueAtRisk"]),
        "equityExposure": _clamp01(equity_exposure),
        "concentration": _clamp01(_normalized_hhi(w)),
        "assetClassConcentration": _clamp01(list(class_exposure.values()) and _normalized_hhi(list(class_exposure.values()))),
        "illiquidity": _clamp01(1.0 - weighted_liquidity),
    }

    components = []
    for key, weight in COMPONENT_WEIGHTS.items():
        components.append(
            {
                "key": key,
                "weight": weight,
                "normalized": round(raw[key], 4),
                "contribution": round(raw[key] * weight * 100.0, 2),
            }
        )
    score = float(sum(c["contribution"] for c in components))
    score = float(min(max(score, 0.0), 100.0))
    return {
        "score": round(score, 1),
        "band": risk_band(score),
        "components": components,
        "inputs": {
            "volatility": volatility,
            "maxDrawdown": max_drawdown,
            "downsideDeviation": downside_deviation,
            "dailyVaR": daily_var,
            "equityExposure": round(equity_exposure, 4),
            "effectiveAssets": round(1.0 / _hhi(w), 2) if w.size else 0.0,
            "weightedLiquidity": round(weighted_liquidity, 3),
        },
    }
