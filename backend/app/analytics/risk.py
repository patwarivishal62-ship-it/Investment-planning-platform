"""Risk metrics: volatility, drawdown, downside risk, VaR/CVaR, ratios.

Historical vs model-based metrics are kept in *separate* functions and are
labelled accordingly by the API layer so a model-based number is never
presented as an observed historical fact.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import returns as ret
from .statistics import kurtosis, skewness

__all__ = [
    "annualized_volatility",
    "downside_deviation",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "drawdown_series",
    "max_drawdown",
    "drawdown_table",
    "recovery_days",
    "ulcer_index",
    "historical_var",
    "historical_cvar",
    "parametric_var",
    "parametric_cvar",
    "risk_metrics_summary",
]


# ---------------------------------------------------------------- volatility


def annualized_volatility(returns, periods_per_year: int = 252, ddof: int = 1) -> float:
    """sigma * sqrt(periods_per_year); the trading-period assumption is explicit."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size <= ddof or periods_per_year <= 0:
        return float("nan")
    var = float(np.var(r, ddof=ddof))
    return float(np.sqrt(max(var, 0.0)) * np.sqrt(periods_per_year))


# ------------------------------------------------------------ downside risk


def downside_deviation(
    returns,
    mar: float = 0.0,
    periods_per_year: int = 252,
    annualize: bool = True,
) -> float:
    """sqrt( mean( min(r - MAR, 0)^2 ) ) over the *full* sample.

    MAR is expressed as a periodic (e.g. daily) threshold. The full-sample
    convention (rather than dividing by the count of downside observations
    only) is used: it is the standard Sortino/Satchell definition and keeps
    the metric comparable across assets.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return float("nan")
    shortfall = np.minimum(r - mar, 0.0)
    dd = float(np.sqrt(np.mean(shortfall**2)))
    if annualize:
        dd *= np.sqrt(periods_per_year)
    return float(dd)


def historical_var(returns, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Historical VaR as a positive loss magnitude.

    Non-parametric: the empirical quantile of realised returns, optionally
    scaled to a multi-day horizon by sqrt(time) (that scaling is a model
    assumption -- see ``parametric_var`` for the fully model-based version).
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0 or not 0.0 < confidence < 1.0:
        return float("nan")
    q = float(np.quantile(r, 1.0 - confidence))
    loss = -q
    if horizon_days > 1:
        loss *= np.sqrt(horizon_days)
    return float(max(loss, 0.0))


def historical_cvar(returns, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Historical Expected Shortfall: mean loss beyond the VaR quantile."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0 or not 0.0 < confidence < 1.0:
        return float("nan")
    threshold = float(np.quantile(r, 1.0 - confidence))
    tail = r[r <= threshold]
    if tail.size == 0:
        return historical_var(r, confidence, horizon_days)
    loss = -float(np.mean(tail))
    if horizon_days > 1:
        loss *= np.sqrt(horizon_days)
    return float(max(loss, 0.0))


def parametric_var(returns, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Gaussian (variance-covariance) VaR -- MODEL-BASED."""
    from scipy import stats

    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 2:
        return float("nan")
    mu, sigma = float(np.mean(r)), float(np.std(r, ddof=1))
    z = float(stats.norm.ppf(1.0 - confidence))
    loss = -(mu + z * sigma)
    if horizon_days > 1:
        loss *= np.sqrt(horizon_days)
    return float(max(loss, 0.0))


def parametric_cvar(returns, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Gaussian Expected Shortfall -- MODEL-BASED."""
    from scipy import stats

    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 2:
        return float("nan")
    mu, sigma = float(np.mean(r)), float(np.std(r, ddof=1))
    alpha = 1.0 - confidence
    z = float(stats.norm.ppf(alpha))
    loss = -(mu - sigma * float(stats.norm.pdf(z)) / alpha)
    if horizon_days > 1:
        loss *= np.sqrt(horizon_days)
    return float(max(loss, 0.0))


# ------------------------------------------------------------------ drawdown


def drawdown_series(equity_curve) -> np.ndarray:
    """Percentage decline from the running peak. Always <= 0."""
    eq = np.asarray(equity_curve, dtype=float)
    if eq.size == 0:
        return np.array([], dtype=float)
    peaks = np.maximum.accumulate(eq)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(peaks > 0, eq / peaks - 1.0, 0.0)
    return np.minimum(dd, 0.0)


def max_drawdown(equity_curve) -> float:
    """Worst peak-to-trough decline. Guaranteed <= 0."""
    dd = drawdown_series(equity_curve)
    return float(np.min(dd)) if dd.size else float("nan")


def _drawdown_episodes(equity_curve) -> list[tuple[int, int, float]]:
    """Return [(start_idx, trough_idx, depth)] for every peak-to-trough episode."""
    eq = np.asarray(equity_curve, dtype=float)
    if eq.size == 0:
        return []
    peaks = np.maximum.accumulate(eq)
    episodes: list[tuple[int, int, float]] = []
    in_dd = False
    start = 0
    trough = 0
    for i in range(eq.size):
        if peaks[i] > 0 and eq[i] < peaks[i] - 1e-15:
            if not in_dd:
                in_dd = True
                start = i
                trough = i
            elif eq[i] < eq[trough]:
                trough = i
        elif in_dd:
            episodes.append((start, trough, float(eq[trough] / peaks[trough] - 1.0)))
            in_dd = False
    if in_dd:
        episodes.append((start, trough, float(eq[trough] / peaks[trough] - 1.0)))
    return episodes


def drawdown_table(equity_curve, dates: pd.DatetimeIndex | None = None, top: int = 5) -> list[dict]:
    """Deepest drawdown episodes with peak date, trough date and recovery date."""
    eq = np.asarray(equity_curve, dtype=float)
    episodes = _drawdown_episodes(eq)
    rows = []
    for start, trough, depth in episodes:
        peak_value = float(eq[start - 1]) if start > 0 else float(eq[0])
        rec_idx = None
        for j in range(trough, eq.size):
            if eq[j] >= peak_value - 1e-12:
                rec_idx = j
                break
        rows.append(
            {
                "depth": float(min(depth, 0.0)),
                "peakIndex": int(start),
                "troughIndex": int(trough),
                "recoveryIndex": rec_idx,
                "lengthPeriods": int(trough - start + 1),
                "recoveryPeriods": (int(rec_idx - trough) if rec_idx is not None else None),
                "recovered": rec_idx is not None,
                "peakDate": (str(dates[start].date()) if dates is not None and start < len(dates) else None),
                "troughDate": (str(dates[trough].date()) if dates is not None and trough < len(dates) else None),
                "recoveryDate": (
                    str(dates[rec_idx].date()) if rec_idx is not None and dates is not None and rec_idx < len(dates) else None
                ),
            }
        )
    rows.sort(key=lambda r: r["depth"])
    return rows[:top]


def recovery_days(equity_curve, periods_per_year: int = 252) -> float | None:
    """Periods needed to climb back from the worst drawdown trough to the old peak."""
    eq = np.asarray(equity_curve, dtype=float)
    episodes = _drawdown_episodes(eq)
    if not episodes:
        return 0.0
    start, trough, _ = max(episodes, key=lambda e: abs(e[2]))
    peak_value = float(eq[start - 1]) if start > 0 else float(eq[0])
    for j in range(trough, eq.size):
        if eq[j] >= peak_value - 1e-12:
            return float(j - trough)
    return None  # never recovered inside the sample


def ulcer_index(equity_curve) -> float:
    """RMS drawdown -- penalises depth *and* duration of drawdowns."""
    dd = drawdown_series(equity_curve)
    if dd.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(dd**2)))


# -------------------------------------------------------------------- ratios


def sharpe_ratio(annual_return: float, annual_volatility: float, risk_free_rate: float = 0.0) -> float:
    """(R - Rf) / sigma. Undefined (NaN) when volatility is zero and R != Rf."""
    if annual_return is None or not np.isfinite(annual_return):
        return float("nan")
    if annual_volatility is None or not np.isfinite(annual_volatility) or annual_volatility <= 0:
        excess = annual_return - risk_free_rate
        return 0.0 if abs(excess) < 1e-15 else float("nan")
    return float((annual_return - risk_free_rate) / annual_volatility)


def sortino_ratio(
    annual_return: float,
    downside_dev: float,
    risk_free_rate: float = 0.0,
) -> float:
    """(R - Rf) / downside deviation. NaN when downside deviation is zero and R != Rf."""
    if annual_return is None or not np.isfinite(annual_return):
        return float("nan")
    if downside_dev is None or not np.isfinite(downside_dev) or downside_dev <= 0:
        excess = annual_return - risk_free_rate
        return 0.0 if abs(excess) < 1e-15 else float("nan")
    return float((annual_return - risk_free_rate) / downside_dev)


def calmar_ratio(cagr_value: float, max_dd: float) -> float:
    """CAGR / |MaxDrawdown|. NaN when there was no drawdown."""
    if cagr_value is None or max_dd is None:
        return float("nan")
    if not np.isfinite(cagr_value) or not np.isfinite(max_dd):
        return float("nan")
    if max_dd >= 0:
        return float("nan")
    return float(cagr_value / abs(max_dd))


# ------------------------------------------------------------------ summary


def risk_metrics_summary(
    periodic_returns: np.ndarray,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
    mar_periodic: float = 0.0,
    confidence: float = 0.95,
    prices: np.ndarray | None = None,
    return_method: str = "arithmetic",
) -> dict:
    """One-call bundle of the headline risk/return metrics for a return series."""
    r = np.asarray(periodic_returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return {"observations": 0}

    ann_ret = ret.annualized_return(r, periods_per_year, method=return_method)
    vol = annualized_volatility(r, periods_per_year)
    dd_dev = downside_deviation(r, mar=mar_periodic, periods_per_year=periods_per_year)

    if prices is not None and np.asarray(prices).size:
        curve = np.asarray(prices, dtype=float)
    else:
        curve = np.cumprod(1.0 + r)

    mdd = max_drawdown(curve)
    growth = float(np.prod(1.0 + r))
    years = r.size / periods_per_year
    cagr_value = ret.cagr(1.0, growth, years) if years > 0 else float("nan")

    return {
        "observations": int(r.size),
        "annualizedReturn": ann_ret,
        "cagr": cagr_value,
        "cumulativeReturn": float(growth - 1.0),
        "volatility": vol,
        "downsideDeviation": dd_dev,
        "sharpe": sharpe_ratio(ann_ret, vol, risk_free_rate),
        "sortino": sortino_ratio(ann_ret, dd_dev, risk_free_rate),
        "calmar": calmar_ratio(cagr_value, mdd),
        "maxDrawdown": mdd,
        "ulcerIndex": ulcer_index(curve),
        "historicalVaR": historical_var(r, confidence),
        "historicalCVaR": historical_cvar(r, confidence),
        "parametricVaR": parametric_var(r, confidence),
        "parametricCVaR": parametric_cvar(r, confidence),
        "skewness": float(skewness(r)),
        "kurtosis": float(kurtosis(r)),
        "bestPeriod": float(np.max(r)),
        "worstPeriod": float(np.min(r)),
        "positivePeriods": int(np.sum(r > 0)),
        "recoveryPeriods": recovery_days(curve, periods_per_year),
    }
