"""Vectorised metrics for thousands of candidate portfolios at once.

Computing drawdown / CVaR per candidate one at a time would be O(K) Python
loops over a T-length series. Because every candidate shares the same return
matrix, we can build the whole (T x K) portfolio-return matrix once and use
axis-wise NumPy reductions, which is what makes scoring tens of thousands of
portfolios practical in a request.
"""
from __future__ import annotations

import numpy as np

__all__ = ["batch_portfolio_returns", "batch_metrics"]


def batch_portfolio_returns(returns: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """(T x N) returns @ (N x K) weights -> (T x K) portfolio returns."""
    return np.asarray(returns, dtype=float) @ np.asarray(weights, dtype=float).T


def batch_metrics(
    returns: np.ndarray,
    weights: np.ndarray,
    mu: np.ndarray,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
    confidence: float = 0.95,
    mar_periodic: float | None = None,
) -> dict[str, np.ndarray]:
    """Path-dependent metrics for every candidate, computed column-wise."""
    r = batch_portfolio_returns(returns, weights)          # (T x K)
    t, k = r.shape
    if t == 0 or k == 0:
        empty = np.array([])
        return {"expectedReturn": empty, "volatility": empty, "maxDrawdown": empty}

    mar = float(risk_free_rate / periods_per_year if mar_periodic is None else mar_periodic)
    expected = np.asarray(weights, dtype=float) @ np.asarray(mu, dtype=float)
    volatility = np.sqrt(np.maximum(np.var(r, axis=0, ddof=1) * periods_per_year, 0.0))

    curve = np.cumprod(1.0 + r, axis=0)
    peaks = np.maximum.accumulate(curve, axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peaks > 0, curve / peaks - 1.0, 0.0)
    max_drawdown = np.min(dd, axis=0)
    ulcer = np.sqrt(np.mean(np.minimum(dd, 0.0) ** 2, axis=0))

    downside = np.sqrt(np.mean(np.minimum(r - mar, 0.0) ** 2, axis=0)) * np.sqrt(periods_per_year)

    sorted_r = np.sort(r, axis=0)
    tail = max(int(np.floor((1.0 - confidence) * t)), 1)
    var = -sorted_r[tail - 1]
    cvar = -np.mean(sorted_r[:tail], axis=0)

    growth = curve[-1]
    years = t / periods_per_year
    with np.errstate(invalid="ignore"):
        cagr = np.where(growth > 0, growth ** (1.0 / years) - 1.0, np.nan) if years > 0 else np.full(k, np.nan)

    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = np.where(volatility > 1e-12, (expected - risk_free_rate) / np.where(volatility > 1e-12, volatility, 1.0), np.nan)
        sortino = np.where(downside > 1e-12, (expected - risk_free_rate) / np.where(downside > 1e-12, downside, 1.0), np.nan)
        calmar = np.where(np.abs(max_drawdown) > 1e-12, cagr / np.abs(max_drawdown), np.nan)

    return {
        "expectedReturn": expected,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "cagr": cagr,
        "maxDrawdown": np.minimum(max_drawdown, 0.0),
        "ulcerIndex": ulcer,
        "downsideDeviation": downside,
        "historicalVaR": np.maximum(var, 0.0),
        "historicalCVaR": np.maximum(cvar, 0.0),
        "finalGrowth": growth,
    }
