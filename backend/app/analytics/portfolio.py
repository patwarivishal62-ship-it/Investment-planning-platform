"""Portfolio mathematics.

E(Rp) = sum_i w_i E(R_i)
sigma_p^2 = w' Sigma w          (clamped to >= 0 against floating point noise)
sigma_p   = sqrt(w' Sigma w)

Risk contribution uses Euler decomposition:
    sigma_p   = sum_i w_i * (Sigma w)_i / sigma_p
so the component contributions sum exactly to portfolio volatility.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "consolidate_weights",
    "normalize_weights",
    "validate_weights",
    "portfolio_expected_return",
    "portfolio_variance",
    "portfolio_volatility",
    "portfolio_returns",
    "diversification_ratio",
    "effective_n",
    "herfindahl_index",
    "risk_contribution",
    "asset_class_exposure",
    "marginal_risk_contribution",
]


def consolidate_weights(
    weights,
    min_weight: float = 0.02,
    class_of: dict[str, str] | None = None,
    class_bounds: dict[str, tuple[float, float]] | None = None,
) -> np.ndarray:
    """Drop economically meaningless holdings and renormalise.

    A mean-variance optimum over 26 assets tends to spread 1-3% across almost
    everything, which is mathematically tidy but not an implementable plan.
    Trimming sub-threshold positions keeps the allocation interpretable.

    Renormalising scales every surviving weight by the same factor, so only an
    *upper* class bound can be breached; if that happens the original weights
    are returned untouched rather than an invalid portfolio.
    """
    w = np.asarray(weights, dtype=float).copy()
    if min_weight <= 0 or w.size == 0:
        return normalize_weights(w)
    keep = w >= min_weight
    if not keep.any() or keep.all():
        return normalize_weights(w)
    trimmed = np.where(keep, w, 0.0)
    if class_of and class_bounds:
        symbols = list(class_of.keys())
        raised = float(1.0 / trimmed.sum())
        exposure: dict[str, float] = {}
        for i, symbol in enumerate(symbols):
            if i >= trimmed.size:
                break
            cls = class_of.get(symbol, "other")
            exposure[cls] = exposure.get(cls, 0.0) + trimmed[i] * raised
        for cls, bounds in class_bounds.items():
            hi = bounds[1] if isinstance(bounds, (list, tuple)) else None
            if hi is not None and exposure.get(cls, 0.0) > hi + 1e-6:
                return normalize_weights(w)
    return normalize_weights(trimmed)


def normalize_weights(weights) -> np.ndarray:
    """Scale weights so they sum to exactly 1. Negative weights are rejected first."""
    w = np.asarray(weights, dtype=float)
    if np.any(w < -1e-12):
        raise ValueError("negative weights are not supported")
    w = np.clip(w, 0.0, None)
    total = float(w.sum())
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return w / total


def validate_weights(weights, tolerance: float = 1e-6) -> bool:
    w = np.asarray(weights, dtype=float)
    return bool(np.all(w >= -tolerance) and abs(float(w.sum()) - 1.0) <= 1e-4)


def portfolio_expected_return(weights, expected_returns) -> float:
    w = np.asarray(weights, dtype=float)
    mu = np.asarray(expected_returns, dtype=float)
    if w.shape != mu.shape:
        raise ValueError("weights and expected returns must have the same shape")
    return float(w @ mu)


def portfolio_variance(weights, covariance) -> float:
    """w' Sigma w, floored at zero so numerical noise can never make it negative."""
    w = np.asarray(weights, dtype=float)
    sigma = np.asarray(covariance, dtype=float)
    if w.shape[0] != sigma.shape[0]:
        raise ValueError("weights and covariance dimensions disagree")
    value = float(w @ sigma @ w)
    if not np.isfinite(value):
        return float("nan")
    return float(max(value, 0.0))


def portfolio_volatility(weights, covariance) -> float:
    return float(np.sqrt(portfolio_variance(weights, covariance)))


def portfolio_returns(asset_returns: np.ndarray, weights) -> np.ndarray:
    """Constant-weight (i.e. continuously rebalanced) portfolio return series."""
    r = np.asarray(asset_returns, dtype=float)
    w = np.asarray(weights, dtype=float)
    if r.ndim != 2 or r.shape[1] != w.shape[0]:
        raise ValueError("asset_returns must be (T x N) and match weights length")
    return r @ w


def diversification_ratio(weights, asset_vols, covariance) -> float:
    """(w . sigma_i) / sigma_p -- >1 means diversification is reducing risk."""
    w = np.asarray(weights, dtype=float)
    vols = np.asarray(asset_vols, dtype=float)
    sigma_p = portfolio_volatility(w, covariance)
    if sigma_p <= 0:
        return float("nan")
    return float((w @ vols) / sigma_p)


def herfindahl_index(weights) -> float:
    w = np.asarray(weights, dtype=float)
    return float(np.sum(w**2))


def effective_n(weights) -> float:
    """1 / HHI -- the 'number of equally weighted positions' equivalent."""
    hhi = herfindahl_index(weights)
    return float(1.0 / hhi) if hhi > 0 else float("nan")


def marginal_risk_contribution(weights, covariance) -> np.ndarray:
    """d sigma_p / d w_i  ==  (Sigma w)_i / sigma_p."""
    w = np.asarray(weights, dtype=float)
    sigma = np.asarray(covariance, dtype=float)
    sigma_p = portfolio_volatility(w, sigma)
    if sigma_p <= 0:
        return np.zeros_like(w)
    return (sigma @ w) / sigma_p


def risk_contribution(weights, covariance, symbols: list[str] | None = None) -> list[dict]:
    """Per-asset risk decomposition.

    Returns marginal contribution, component contribution (w_i * MCR_i) and
    the share of total portfolio volatility each asset is responsible for.
    Component contributions sum to portfolio volatility (Euler's theorem).
    """
    w = np.asarray(weights, dtype=float)
    sigma = np.asarray(covariance, dtype=float)
    sigma_p = portfolio_volatility(w, sigma)
    mcr = marginal_risk_contribution(w, sigma)
    rc = w * mcr
    total = float(rc.sum())
    rows = []
    for i in range(w.shape[0]):
        rows.append(
            {
                "symbol": symbols[i] if symbols else f"asset_{i}",
                "weight": float(w[i]),
                "marginalRiskContribution": float(mcr[i]),
                "riskContribution": float(rc[i]),
                "riskShare": float(rc[i] / total) if abs(total) > 1e-15 else 0.0,
                "volatility": float(np.sqrt(max(sigma[i, i], 0.0))),
            }
        )
    rows.sort(key=lambda r: r["riskContribution"], reverse=True)
    result = {
        "portfolioVolatility": sigma_p,
        "contributions": rows,
    }
    return result


def asset_class_exposure(weights, symbols: list[str], class_of: dict[str, str]) -> dict[str, float]:
    w = np.asarray(weights, dtype=float)
    out: dict[str, float] = {}
    for i, sym in enumerate(symbols):
        cls = class_of.get(sym, "other")
        out[cls] = out.get(cls, 0.0) + float(w[i])
    return out
