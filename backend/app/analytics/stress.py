"""Stress testing: assumption-based scenarios and observed historical windows.

Two clearly separated families:
  * ``scenario`` -- user-editable hypothetical shocks. Labelled ILLUSTRATIVE.
  * ``historical`` -- replay of the worst realised windows in the data.
    Labelled OBSERVED (past fact, still not a prediction).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["SCENARIOS", "apply_scenario", "historical_stress_windows", "replay_window"]


SCENARIOS: dict[str, dict] = {
    "equity_crash": {
        "name": "Equity Crash",
        "description": "A sharp, broad-based fall in equity markets.",
        "shocks": [
            {"scope": "assetClass", "target": "equity", "shock": -0.30},
            {"scope": "assetClass", "target": "international_equity", "shock": -0.25},
            {"scope": "assetClass", "target": "gold", "shock": 0.05},
            {"scope": "assetClass", "target": "bond", "shock": 0.02},
            {"scope": "assetClass", "target": "cash", "shock": 0.0},
            {"scope": "assetClass", "target": "commodity", "shock": -0.15},
        ],
    },
    "inflation_shock": {
        "name": "Inflation Shock",
        "description": "Unexpectedly high inflation; commodities bid up, long bonds pressured.",
        "shocks": [
            {"scope": "assetClass", "target": "equity", "shock": -0.10},
            {"scope": "assetClass", "target": "gold", "shock": 0.12},
            {"scope": "assetClass", "target": "commodity", "shock": 0.20},
            {"scope": "assetClass", "target": "bond", "shock": -0.08},
            {"scope": "assetClass", "target": "cash", "shock": -0.02},
            {"scope": "assetClass", "target": "international_equity", "shock": -0.08},
        ],
    },
    "rate_shock": {
        "name": "Interest Rate Shock",
        "description": "A sudden rise in interest rates: bond prices fall, equities de-rate.",
        "shocks": [
            {"scope": "assetClass", "target": "bond", "shock": -0.12},
            {"scope": "assetClass", "target": "equity", "shock": -0.08},
            {"scope": "assetClass", "target": "reit", "shock": -0.18},
            {"scope": "assetClass", "target": "gold", "shock": -0.05},
            {"scope": "assetClass", "target": "cash", "shock": 0.01},
        ],
    },
    "commodity_shock": {
        "name": "Commodity Shock",
        "description": "A supply-driven spike then collapse in commodity prices.",
        "shocks": [
            {"scope": "assetClass", "target": "commodity", "shock": -0.30},
            {"scope": "assetClass", "target": "gold", "shock": -0.12},
            {"scope": "assetClass", "target": "equity", "shock": -0.06},
            {"scope": "assetClass", "target": "bond", "shock": 0.01},
        ],
    },
    "recession": {
        "name": "Recession",
        "description": "Broad growth slowdown: equities and commodities fall, bonds rally.",
        "shocks": [
            {"scope": "assetClass", "target": "equity", "shock": -0.22},
            {"scope": "assetClass", "target": "international_equity", "shock": -0.20},
            {"scope": "assetClass", "target": "commodity", "shock": -0.18},
            {"scope": "assetClass", "target": "reit", "shock": -0.25},
            {"scope": "assetClass", "target": "bond", "shock": 0.06},
            {"scope": "assetClass", "target": "gold", "shock": 0.08},
            {"scope": "assetClass", "target": "cash", "shock": 0.0},
        ],
    },
    "liquidity_crisis": {
        "name": "Liquidity Crisis",
        "description": "Correlations converge toward 1 as investors raise cash.",
        "shocks": [
            {"scope": "assetClass", "target": "equity", "shock": -0.25},
            {"scope": "assetClass", "target": "gold", "shock": -0.10},
            {"scope": "assetClass", "target": "commodity", "shock": -0.22},
            {"scope": "assetClass", "target": "reit", "shock": -0.30},
            {"scope": "assetClass", "target": "bond", "shock": -0.02},
            {"scope": "assetClass", "target": "cash", "shock": 0.0},
        ],
    },
}


def apply_scenario(
    weights,
    symbols: list[str],
    class_of: dict[str, str],
    shocks: list[dict],
    value: float = 1.0,
) -> dict:
    """Apply hypothetical shocks to a portfolio.

    The model is deliberately simple and transparent: each asset receives the
    shock assigned to its asset class (or symbol/sector if specified), and the
    portfolio impact is the weighted sum. It assumes the shock happens
    instantaneously and that nothing else changes.
    """
    w = np.asarray(weights, dtype=float)
    # More specific scopes win over broader ones.
    symbol_shocks: dict[str, float] = {}
    sector_shocks: dict[str, float] = {}
    class_shocks: dict[str, float] = {}
    sector_of: dict[str, str] = {}
    for shock in shocks:
        scope = shock.get("scope", "assetClass")
        target = shock.get("target")
        amount = float(shock.get("shock", 0.0))
        if scope in ("symbol", "asset"):
            symbol_shocks[target] = amount
        elif scope == "sector":
            sector_shocks[target] = amount
        else:
            class_shocks[target] = amount

    per_asset = []
    for i, sym in enumerate(symbols):
        if sym in symbol_shocks:
            amount = symbol_shocks[sym]
            applied = "symbol"
        elif sector_of.get(sym) in sector_shocks:
            amount = sector_shocks[sector_of[sym]]
            applied = "sector"
        else:
            amount = class_shocks.get(class_of.get(sym, "other"), 0.0)
            applied = "assetClass"
        per_asset.append(
            {
                "symbol": sym,
                "weight": float(w[i]),
                "assetClass": class_of.get(sym, "other"),
                "shock": float(amount),
                "appliedBy": applied,
                "contribution": float(w[i] * amount),
            }
        )

    impact = float(sum(a["contribution"] for a in per_asset))
    return {
        "portfolioImpact": impact,
        "portfolioImpactPct": impact,
        "stressedValue": float(value) * (1.0 + impact),
        "valueBefore": float(value),
        "valueAfter": float(value) * (1.0 + impact),
        "assets": sorted(per_asset, key=lambda a: a["contribution"]),
        "basis": "illustrative",
        "caveat": (
            "Hypothetical instantaneous shock based on the assumptions shown. "
            "It is not a forecast and assumes no other market changes."
        ),
    }


def historical_stress_windows(
    portfolio_returns: pd.Series | np.ndarray,
    dates: pd.DatetimeIndex | None = None,
    window_days: int = 60,
    top: int = 6,
) -> list[dict]:
    """Worst realised rolling windows in the historical record."""
    r = pd.Series(np.asarray(portfolio_returns, dtype=float))
    if dates is not None and len(dates) == len(r):
        r.index = pd.DatetimeIndex(dates)
    if len(r) < window_days:
        return []
    rolled = (1.0 + r).rolling(window_days).apply(np.prod, raw=True) - 1.0
    rolled = rolled.dropna()
    if rolled.empty:
        return []
    worst = rolled.nsmallest(top)
    out = []
    for ts, value in worst.items():
        end_loc = r.index.get_loc(ts)
        start_loc = max(0, int(end_loc) - window_days + 1)
        out.append(
            {
                "label": f"{window_days}-day window ending {_fmt_date(ts)}",
                "startDate": _fmt_date(r.index[start_loc]),
                "endDate": _fmt_date(ts),
                "return": float(value),
                "windowDays": window_days,
            }
        )
    return out


def replay_window(
    weights,
    asset_returns: pd.DataFrame,
    start: str,
    end: str,
) -> dict:
    """Replay a portfolio through a named historical window using realised returns."""
    window = asset_returns.loc[start:end]
    if window.empty:
        return {}
    w = np.asarray(weights, dtype=float)
    port = window.to_numpy(dtype=float) @ w
    curve = np.cumprod(1.0 + np.nan_to_num(port, nan=0.0))
    peaks = np.maximum.accumulate(curve)
    dd = float(np.min(np.where(peaks > 0, curve / peaks - 1.0, 0.0)))
    return {
        "start": str(window.index[0].date()),
        "end": str(window.index[-1].date()),
        "periods": int(len(window)),
        "cumulativeReturn": float(curve[-1] - 1.0),
        "maxDrawdown": dd,
        "annualizedReturn": float(curve[-1] ** (252.0 / max(len(window), 1)) - 1.0) if len(window) else float("nan"),
        "equityCurve": [float(v) for v in curve],
        "dates": [str(d.date()) for d in window.index],
        "basis": "observed",
    }


def _fmt_date(ts) -> str:
    try:
        return str(pd.Timestamp(ts).date())
    except Exception:  # pragma: no cover
        return str(ts)
