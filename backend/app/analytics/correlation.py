"""Correlation engine: Pearson / covariance / rolling correlation."""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "pearson_correlation_matrix",
    "covariance_matrix",
    "correlation_series",
    "rolling_correlation",
    "portfolio_correlation_series",
    "nearest_psd",
    "average_pairwise_correlation",
]


def pearson_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pairwise-complete Pearson correlation. Values are clipped to [-1, 1]."""
    if returns.empty:
        return returns
    corr = returns.corr(method="pearson", min_periods=2)
    return corr.clip(-1.0, 1.0)


def covariance_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Sample covariance matrix, annualisation left to the caller."""
    return returns.cov(min_periods=2)


def correlation_series(a: pd.Series, b: pd.Series, window: int | None = None) -> pd.Series:
    """Rolling (or full-sample when window is None) correlation of two series."""
    if window is None:
        joined = pd.concat([a, b], axis=1).dropna()
        if len(joined) < 2:
            return pd.Series(dtype=float)
        value = float(np.corrcoef(joined.iloc[:, 0], joined.iloc[:, 1])[0, 1])
        return pd.Series([value], index=[joined.index[-1] if len(joined.index) else 0])
    return a.rolling(window).corr(b)


def rolling_correlation(returns: pd.DataFrame, a: str, b: str, window: int = 90) -> pd.Series:
    if a not in returns.columns or b not in returns.columns:
        raise KeyError(f"unknown symbol(s): {a}, {b}")
    return correlation_series(returns[a], returns[b], window).dropna()


def portfolio_correlation_series(
    returns: pd.DataFrame, portfolio_returns: pd.Series, window: int = 90
) -> pd.DataFrame:
    """Rolling correlation of every asset against the portfolio's own returns."""
    out = {}
    for col in returns.columns:
        s = portfolio_returns.rolling(window).corr(returns[col])
        out[col] = s
    return pd.DataFrame(out)


def average_pairwise_correlation(corr: pd.DataFrame) -> float:
    """Mean of the off-diagonal correlations -- a crude diversification read."""
    if corr.empty or corr.shape[0] < 2:
        return float("nan")
    m = corr.to_numpy(dtype=float)
    n = m.shape[0]
    off = m[~np.eye(n, dtype=bool)]
    off = off[np.isfinite(off)]
    return float(np.mean(off)) if off.size else float("nan")


def nearest_psd(matrix: np.ndarray, epsilon: float = 1e-10) -> np.ndarray:
    """Project a covariance matrix onto the positive semi-definite cone.

    Guards against tiny negative eigenvalues produced by floating point noise
    or by missing-data pairwise covariance, which would otherwise make
    portfolio variance negative.
    """
    m = np.asarray(matrix, dtype=float)
    m = (m + m.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(m)
    eigenvalues = np.clip(eigenvalues, epsilon, None)
    return (eigenvectors * eigenvalues) @ eigenvectors.T
