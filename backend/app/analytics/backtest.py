"""Backtesting engine with explicit rebalancing and configurable costs.

Look-ahead bias control
-----------------------
The simulator walks forward one period at a time. At period ``t`` it only uses
the asset returns realised at ``t`` (already known once the period closes) and
weights carried from ``t-1``. Rebalancing decisions at ``t`` use the target
weights supplied by the caller -- which, for an honest study, must come from an
optimisation run whose training window ends *before* ``t``. The walk-forward
module enforces that by re-optimising on an expanding/contracting window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from .portfolio import normalize_weights

__all__ = ["BacktestResult", "simulate_portfolio", "REBALANCE_RULES"]

RebalanceFrequency = Literal["none", "monthly", "quarterly", "semiannual", "annual", "threshold"]


@dataclass
class BacktestResult:
    dates: list[str]
    equity: np.ndarray
    returns: np.ndarray
    weights_history: np.ndarray
    turnover: np.ndarray
    rebalance_dates: list[str]
    contribution_dates: list[str]
    total_contributions: float
    total_costs: float
    total_turnover: float
    initial_value: float
    final_value: float
    metadata: dict = field(default_factory=dict)

    @property
    def periods(self) -> int:
        return int(self.equity.size)


def _rebalance_mask(dates: pd.DatetimeIndex, frequency: RebalanceFrequency) -> np.ndarray:
    """Boolean mask of dates on which a calendar rebalance occurs."""
    if frequency == "none":
        return np.zeros(len(dates), dtype=bool)
    if frequency == "monthly":
        return _period_change_mask(dates, lambda d: (d.year, d.month))
    if frequency == "quarterly":
        return _period_change_mask(dates, lambda d: (d.year, (d.month - 1) // 3))
    if frequency == "semiannual":
        return _period_change_mask(dates, lambda d: (d.year, (d.month - 1) // 6))
    if frequency == "annual":
        return _period_change_mask(dates, lambda d: d.year)
    if frequency == "threshold":
        return np.zeros(len(dates), dtype=bool)
    raise ValueError(f"unknown rebalance frequency: {frequency!r}")


def _period_change_mask(dates: pd.DatetimeIndex, key) -> np.ndarray:
    mask = np.zeros(len(dates), dtype=bool)
    mask[0] = True
    for i in range(1, len(dates)):
        if key(dates[i]) != key(dates[i - 1]):
            mask[i] = True
    return mask


def _contribution_mask(dates: pd.DatetimeIndex, frequency: str) -> np.ndarray:
    """Monthly contributions land on the last trading day of each month."""
    if frequency in (None, "", "none"):
        return np.zeros(len(dates), dtype=bool)
    if frequency == "monthly":
        return _period_change_mask(dates, lambda d: (d.year, d.month))
    if frequency == "quarterly":
        return _period_change_mask(dates, lambda d: (d.year, (d.month - 1) // 3))
    if frequency == "annual":
        return _period_change_mask(dates, lambda d: d.year)
    return _period_change_mask(dates, lambda d: (d.year, d.month))


def simulate_portfolio(
    asset_returns: pd.DataFrame,
    weights,
    initial_value: float = 1_000_000.0,
    periodic_contribution: float = 0.0,
    contribution_frequency: str = "monthly",
    rebalance_frequency: RebalanceFrequency = "quarterly",
    rebalance_threshold: float = 0.10,
    transaction_cost_bps: float = 10.0,
    cost_on_contributions: bool = True,
) -> BacktestResult:
    """Walk-forward simulation of a fixed-target-weight portfolio.

    Parameters
    ----------
    asset_returns : T x N frame of periodic (daily) simple returns.
    weights : target weights, length N.
    periodic_contribution : cash added on each contribution date (INR).
    transaction_cost_bps : one-way cost, in basis points of traded notional.
    rebalance_threshold : only used when frequency == "threshold"; an asset is
        traded back to target when its weight drifts by more than this in
        absolute terms (band rebalancing).
    """
    if asset_returns.empty:
        raise ValueError("no return history supplied")
    r = asset_returns.to_numpy(dtype=float)
    r = np.nan_to_num(r, nan=0.0)
    n_assets = r.shape[1]
    w = normalize_weights(weights)
    if w.shape[0] != n_assets:
        raise ValueError("weights length must equal number of assets")

    dates = pd.DatetimeIndex(asset_returns.index)
    cost_rate = float(transaction_cost_bps) / 10_000.0
    calendar_mask = _rebalance_mask(dates, rebalance_frequency)
    contrib_mask = _contribution_mask(dates, contribution_frequency)

    value = float(initial_value)
    cur_w = w.copy()
    equity = np.empty(len(dates), dtype=float)
    returns = np.empty(len(dates), dtype=float)
    weights_hist = np.empty((len(dates), n_assets), dtype=float)
    turnover_series = np.zeros(len(dates), dtype=float)
    rebalance_dates: list[str] = []
    contribution_dates: list[str] = []
    total_costs = 0.0
    total_contrib = 0.0

    for t in range(len(dates)):
        # 1. Contributions are injected at the start of the period, at target.
        if contrib_mask[t] and periodic_contribution:
            if value <= 0:
                value = float(periodic_contribution)
                cur_w = w.copy()
            else:
                invested = np.maximum(cur_w * value, 0.0)
                total_pre = invested.sum()
                added = w * float(periodic_contribution)
                new_total = total_pre + float(periodic_contribution)
                cur_w = (invested + added) / new_total
                value = new_total
                if cost_on_contributions:
                    cost = float(periodic_contribution) * cost_rate
                    value -= cost
                    total_costs += cost
            total_contrib += float(periodic_contribution)
            contribution_dates.append(str(dates[t].date()))

        # 2. Realise this period's return with the weights carried into it.
        period_return = float(cur_w @ r[t])
        value *= 1.0 + period_return
        drifted = cur_w * (1.0 + r[t])
        s = drifted.sum()
        if s > 0:
            cur_w = drifted / s

        # 3. Rebalance if the rule says so.
        do_rebalance = bool(calendar_mask[t])
        if rebalance_frequency == "threshold":
            do_rebalance = bool(np.any(np.abs(cur_w - w) > rebalance_threshold))
        if do_rebalance and t > 0:
            traded = np.abs(cur_w - w)
            turnover = float(traded.sum())
            if turnover > 1e-12:
                cost = value * turnover * cost_rate
                value -= cost
                total_costs += cost
                turnover_series[t] = turnover
                rebalance_dates.append(str(dates[t].date()))
            cur_w = w.copy()

        equity[t] = value
        returns[t] = period_return
        weights_hist[t] = cur_w

    return BacktestResult(
        dates=[str(d.date()) for d in dates],
        equity=equity,
        returns=returns,
        weights_history=weights_hist,
        turnover=turnover_series,
        rebalance_dates=rebalance_dates,
        contribution_dates=contribution_dates,
        total_contributions=total_contrib,
        total_costs=total_costs,
        total_turnover=float(turnover_series.sum()),
        initial_value=float(initial_value),
        final_value=float(value),
        metadata={
            "rebalanceFrequency": rebalance_frequency,
            "transactionCostBps": float(transaction_cost_bps),
            "periodicContribution": float(periodic_contribution),
            "contributionFrequency": contribution_frequency,
        },
    )
