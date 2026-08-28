"""Descriptive statistics -- implemented explicitly (no hidden defaults)."""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "mean",
    "median",
    "variance",
    "std_dev",
    "skewness",
    "kurtosis",
    "minimum",
    "maximum",
    "quantile",
    "describe",
    "covariance_matrix",
    "zscore",
]


def _clean(values) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    return arr[np.isfinite(arr)]


def mean(values) -> float:
    a = _clean(values)
    return float(np.mean(a)) if a.size else float("nan")


def median(values) -> float:
    a = _clean(values)
    return float(np.median(a)) if a.size else float("nan")


def variance(values, ddof: int = 1) -> float:
    a = _clean(values)
    if a.size <= ddof:
        return float("nan")
    return float(np.var(a, ddof=ddof))


def std_dev(values, ddof: int = 1) -> float:
    v = variance(values, ddof=ddof)
    return float(np.sqrt(v)) if np.isfinite(v) and v >= 0 else float("nan")


def skewness(values) -> float:
    """Adjusted Fisher-Pearson sample skewness (g1, the pandas/SciPy default)."""
    a = _clean(values)
    n = a.size
    if n < 3:
        return float("nan")
    centred = a - a.mean()
    m2 = np.mean(centred**2)
    if m2 <= 0:
        return float("nan")
    m3 = np.mean(centred**3)
    g1 = m3 / m2**1.5
    return float(np.sqrt(n * (n - 1)) / (n - 2) * g1)


def kurtosis(values) -> float:
    """Sample **excess** kurtosis (normal distribution == 0)."""
    a = _clean(values)
    n = a.size
    if n < 4:
        return float("nan")
    centred = a - a.mean()
    m2 = np.mean(centred**2)
    if m2 <= 0:
        return float("nan")
    m4 = np.mean(centred**4)
    g2 = m4 / m2**2 - 3.0
    return float(
        ((n - 1) * ((n + 1) * g2 + 6)) / ((n - 2) * (n - 3))
    )


def minimum(values) -> float:
    a = _clean(values)
    return float(np.min(a)) if a.size else float("nan")


def maximum(values) -> float:
    a = _clean(values)
    return float(np.max(a)) if a.size else float("nan")


def quantile(values, q: float) -> float:
    a = _clean(values)
    if a.size == 0 or not 0.0 <= q <= 1.0:
        return float("nan")
    return float(np.quantile(a, q))


def describe(values) -> dict:
    a = _clean(values)
    return {
        "count": int(a.size),
        "mean": mean(a),
        "median": median(a),
        "variance": variance(a),
        "stdDev": std_dev(a),
        "skewness": skewness(a),
        "kurtosis": kurtosis(a),
        "min": minimum(a),
        "max": maximum(a),
        "p05": quantile(a, 0.05),
        "p25": quantile(a, 0.25),
        "p75": quantile(a, 0.75),
        "p95": quantile(a, 0.95),
    }


def zscore(values) -> np.ndarray:
    a = np.asarray(values, dtype=float)
    sd = std_dev(a)
    if not np.isfinite(sd) or sd == 0:
        return np.zeros_like(a)
    return (a - mean(a)) / sd


def covariance_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Sample covariance (ddof=1) of a T x N return frame, NaN-tolerant per pair."""
    return returns.cov(min_periods=2)
