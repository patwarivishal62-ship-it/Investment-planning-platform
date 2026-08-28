"""Return calculations.

Conventions
-----------
* ``simple``   r_t = P_t / P_{t-1} - 1
* ``log``      r_t = ln(P_t / P_{t-1})

The engine never silently picks one: every call site states the convention.
Compounding / aggregation uses **simple** returns; log returns are provided for
statistical work where additivity is convenient.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SIMPLE = "simple"
LOG = "log"

__all__ = [
    "simple_returns",
    "log_returns",
    "price_returns",
    "returns_frame",
    "require_positive_prices",
    "annualized_return",
    "cagr",
    "cumulative_return",
    "resample_returns",
    "period_returns",
    "rolling_return",
    "PERIODS_PER_YEAR",
]

PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12, "quarterly": 4, "annual": 1}


def require_positive_prices(prices: np.ndarray | pd.Series | pd.DataFrame) -> None:
    """Reject zero / negative / non-finite prices instead of silently repairing them."""
    arr = np.asarray(prices, dtype=float)
    if arr.size == 0:
        return
    if not np.all(np.isfinite(arr)):
        raise ValueError("price series contains non-finite values (NaN or infinity)")
    if np.any(arr <= 0):
        raise ValueError("price series contains zero or negative prices")


def simple_returns(prices: np.ndarray) -> np.ndarray:
    """r_t = P_t / P_{t-1} - 1. Output length == input length, first element is NaN."""
    p = np.asarray(prices, dtype=float)
    if p.ndim != 1:
        raise ValueError("simple_returns expects a 1-D price array")
    if p.size < 2:
        return np.array([], dtype=float)
    require_positive_prices(p[1:])
    out = np.full(p.shape, np.nan, dtype=float)
    out[1:] = p[1:] / p[:-1] - 1.0
    return out


def log_returns(prices: np.ndarray) -> np.ndarray:
    """ln(P_t / P_{t-1}). Output length == input length, first element is NaN."""
    p = np.asarray(prices, dtype=float)
    if p.ndim != 1:
        raise ValueError("log_returns expects a 1-D price array")
    if p.size < 2:
        return np.array([], dtype=float)
    require_positive_prices(p)
    out = np.full(p.shape, np.nan, dtype=float)
    out[1:] = np.log(p[1:] / p[:-1])
    return out


def price_returns(prices: np.ndarray, method: str = SIMPLE) -> np.ndarray:
    if method == LOG:
        return log_returns(prices)
    if method == SIMPLE:
        return simple_returns(prices)
    raise ValueError(f"unknown return convention: {method!r}")


def returns_frame(prices: pd.DataFrame, method: str = SIMPLE) -> pd.DataFrame:
    """Column-wise returns for a price frame (dates x symbols). First row is NaN."""
    if method == LOG:
        out = np.log(prices / prices.shift(1))
    elif method == SIMPLE:
        out = prices / prices.shift(1) - 1.0
    else:
        raise ValueError(f"unknown return convention: {method!r}")
    return out.iloc[1:]


def cumulative_return(returns: np.ndarray) -> float:
    """Total compounded growth over the sample, e.g. 0.42 == +42%."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return float("nan")
    return float(np.prod(1.0 + r) - 1.0)


def annualized_return(
    returns: np.ndarray,
    periods_per_year: int = 252,
    method: str = "arithmetic",
) -> float:
    """Annualise a periodic return series.

    ``arithmetic`` mean(r) * periods_per_year -- the single-period expectation
    used by mean-variance mathematics (E(Rp) = sum_i w_i E(R_i)).
    ``geometric``  (prod(1+r)) ** (periods/n) - 1 -- realised compounding.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0 or periods_per_year <= 0:
        return float("nan")
    if method == "arithmetic":
        return float(np.mean(r) * periods_per_year)
    if method == "geometric":
        growth = float(np.prod(1.0 + r))
        if growth <= 0:
            return float("nan")
        return float(growth ** (periods_per_year / r.size) - 1.0)
    raise ValueError(f"unknown annualization method: {method!r}")


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound annual growth rate. Returns NaN for invalid periods/values."""
    if years is None or years <= 0:
        return float("nan")
    if start_value is None or end_value is None:
        return float("nan")
    if start_value <= 0 or end_value <= 0:
        return float("nan")
    if not (np.isfinite(start_value) and np.isfinite(end_value)):
        return float("nan")
    return float((end_value / start_value) ** (1.0 / years) - 1.0)


def resample_returns(returns: pd.Series | pd.DataFrame, freq: str = "ME") -> pd.Series | pd.DataFrame:
    """Compound periodic returns into a lower frequency (e.g. daily -> monthly)."""
    return (1.0 + returns).resample(freq).prod() - 1.0


def period_returns(returns: pd.Series, freq: str = "YE") -> list[dict]:
    """Calendar-period compounded returns, e.g. per calendar year."""
    compounded = resample_returns(returns, freq)
    out = []
    for ts, value in compounded.items():
        label = str(ts.year) if freq in {"YE", "A"} else str(ts.date())
        out.append({"period": label, "return": float(value)})
    return out


def rolling_return(returns: pd.Series, window: int, periods_per_year: int = 252) -> pd.Series:
    """Rolling annualised (geometric) return over ``window`` observations."""
    if window < 2:
        raise ValueError("rolling window must be >= 2")
    growth = (1.0 + returns).rolling(window).apply(np.prod, raw=True)
    return growth ** (periods_per_year / window) - 1.0
