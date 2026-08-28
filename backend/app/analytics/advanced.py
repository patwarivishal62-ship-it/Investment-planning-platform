"""Advanced analytics: rolling metrics, beta/alpha, capture ratios, PCA."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import risk as riskmod

__all__ = [
    "rolling_volatility",
    "rolling_sharpe",
    "rolling_return",
    "beta_alpha",
    "tracking_error",
    "information_ratio",
    "capture_ratios",
    "principal_components",
    "up_down_capture",
]


def _series(values, index=None) -> pd.Series:
    s = pd.Series(np.asarray(values, dtype=float))
    if index is not None:
        s.index = pd.DatetimeIndex(index)
    return s


def rolling_volatility(returns, window: int = 63, periods_per_year: int = 252) -> pd.Series:
    return _series(returns).rolling(window).std(ddof=1) * np.sqrt(periods_per_year)


def rolling_sharpe(
    returns, window: int = 252, periods_per_year: int = 252, risk_free_rate: float = 0.0
) -> pd.Series:
    s = _series(returns)
    mean = s.rolling(window).mean() * periods_per_year
    vol = s.rolling(window).std(ddof=1) * np.sqrt(periods_per_year)
    return (mean - risk_free_rate) / vol.replace(0.0, np.nan)


def rolling_return(returns, window: int = 252, periods_per_year: int = 252) -> pd.Series:
    s = _series(returns)
    return (1.0 + s).rolling(window).apply(np.prod, raw=True) ** (periods_per_year / window) - 1.0


def beta_alpha(
    returns,
    benchmark_returns,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """CAPM beta and Jensen's alpha, annualised."""
    r = pd.Series(np.asarray(returns, dtype=float))
    b = pd.Series(np.asarray(benchmark_returns, dtype=float))
    joined = pd.concat([r, b], axis=1).dropna()
    if len(joined) < 3:
        return {"beta": float("nan"), "alpha": float("nan"), "rSquared": float("nan"), "observations": 0}
    x = joined.iloc[:, 1].to_numpy()
    y = joined.iloc[:, 0].to_numpy()
    var_x = float(np.var(x, ddof=1))
    if var_x <= 0:
        return {"beta": float("nan"), "alpha": float("nan"), "rSquared": float("nan"), "observations": len(joined)}
    cov_xy = float(np.cov(y, x, ddof=1)[0, 1])
    beta = cov_xy / var_x
    rf_periodic = risk_free_rate / periods_per_year
    alpha_periodic = float(np.mean(y - rf_periodic) - beta * (np.mean(x - rf_periodic)))
    corr = float(np.corrcoef(x, y)[0, 1])
    return {
        "beta": float(beta),
        "alpha": float(alpha_periodic * periods_per_year),
        "rSquared": float(corr**2),
        "correlation": corr,
        "observations": int(len(joined)),
    }


def tracking_error(returns, benchmark_returns, periods_per_year: int = 252) -> float:
    r = pd.Series(np.asarray(returns, dtype=float))
    b = pd.Series(np.asarray(benchmark_returns, dtype=float))
    joined = pd.concat([r, b], axis=1).dropna()
    if len(joined) < 2:
        return float("nan")
    diff = joined.iloc[:, 0] - joined.iloc[:, 1]
    return float(diff.std(ddof=1) * np.sqrt(periods_per_year))


def information_ratio(returns, benchmark_returns, periods_per_year: int = 252) -> float:
    r = pd.Series(np.asarray(returns, dtype=float))
    b = pd.Series(np.asarray(benchmark_returns, dtype=float))
    joined = pd.concat([r, b], axis=1).dropna()
    if len(joined) < 2:
        return float("nan")
    diff = joined.iloc[:, 0] - joined.iloc[:, 1]
    te = float(diff.std(ddof=1))
    if te <= 0:
        return float("nan")
    return float(diff.mean() * periods_per_year / (te * np.sqrt(periods_per_year)))


def capture_ratios(returns, benchmark_returns) -> dict:
    r = pd.Series(np.asarray(returns, dtype=float))
    b = pd.Series(np.asarray(benchmark_returns, dtype=float))
    joined = pd.concat([r, b], axis=1).dropna()
    if joined.empty:
        return {"upsideCapture": float("nan"), "downsideCapture": float("nan")}
    up = joined[joined.iloc[:, 1] > 0]
    down = joined[joined.iloc[:, 1] < 0]
    upside = float(up.iloc[:, 0].mean() / up.iloc[:, 1].mean()) if len(up) and up.iloc[:, 1].mean() != 0 else float("nan")
    downside = (
        float(down.iloc[:, 0].mean() / down.iloc[:, 1].mean()) if len(down) and down.iloc[:, 1].mean() != 0 else float("nan")
    )
    return {"upsideCapture": upside, "downsideCapture": downside, "upPeriods": int(len(up)), "downPeriods": int(len(down))}


def up_down_capture(returns, benchmark_returns) -> dict:
    return capture_ratios(returns, benchmark_returns)


def principal_components(returns: pd.DataFrame, components: int = 3) -> dict:
    """PCA on the standardized return matrix (correlation-based)."""
    if returns.empty:
        return {"explainedVariance": [], "loadings": {}, "components": 0}
    frame = returns.dropna(axis=1, how="all").fillna(0.0)
    if frame.shape[1] < 2:
        return {"explainedVariance": [], "loadings": {}, "components": 0}
    z = (frame - frame.mean()) / frame.std(ddof=1).replace(0.0, np.nan)
    z = z.fillna(0.0).to_numpy(dtype=float)
    cov = np.cov(z, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    total = float(eigenvalues.sum())
    k = int(min(components, eigenvalues.size))
    explained = [float(v / total) if total > 0 else 0.0 for v in eigenvalues[:k]]
    loadings = {
        str(frame.columns[i]): [float(eigenvectors[i, j]) for j in range(k)]
        for i in range(frame.shape[1])
    }
    return {
        "explainedVariance": explained,
        "eigenvalues": [float(v) for v in eigenvalues[:k]],
        "loadings": loadings,
        "components": k,
        "totalVariance": total,
    }
