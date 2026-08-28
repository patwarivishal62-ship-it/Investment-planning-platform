import numpy as np
import pandas as pd
import pytest

from app.analytics.backtest import simulate_portfolio
from app.analytics.portfolio import normalize_weights


def _frame(returns: dict[str, list[float]]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(next(iter(returns.values()))))
    return pd.DataFrame(returns, index=dates)


def test_single_asset_no_contribution_matches_direct_compounding():
    r = [0.01, -0.02, 0.03, 0.005]
    frame = _frame({"A": r})
    result = simulate_portfolio(frame, [1.0], initial_value=100_000.0,
                                rebalance_frequency="none", transaction_cost_bps=0)
    expected = 100_000.0 * np.prod([1 + x for x in r])
    assert result.final_value == pytest.approx(expected)


def test_two_asset_fixed_weights_replicate_manual_calculation():
    """Verifies the period-by-period walk with no look-ahead: the return at t
    uses the weights carried in from t-1."""
    frame = _frame({"A": [0.10, 0.10], "B": [0.0, 0.0]})
    result = simulate_portfolio(frame, [0.5, 0.5], initial_value=100.0,
                                rebalance_frequency="none", transaction_cost_bps=0)
    # Day 1: 0.5*0.10 + 0.5*0 = +5% -> 105. Weights drift to 55 / 45.
    assert result.equity[0] == pytest.approx(105.0)
    w_after_day1 = 0.5 * 1.10 / 1.05
    # Day 2: return = w_A * 0.10
    expected_day2 = 105.0 * (1 + w_after_day1 * 0.10)
    assert result.equity[1] == pytest.approx(expected_day2)


def test_rebalancing_changes_the_outcome():
    r = list(np.random.default_rng(1).normal(0.001, 0.02, 300))
    frame = _frame({"A": r, "B": [-x * 0.5 for x in r]})
    rebalanced = simulate_portfolio(frame, [0.5, 0.5], rebalance_frequency="quarterly",
                                    transaction_cost_bps=0)
    drifted = simulate_portfolio(frame, [0.5, 0.5], rebalance_frequency="none",
                                 transaction_cost_bps=0)
    assert rebalanced.final_value != pytest.approx(drifted.final_value)
    assert len(rebalanced.rebalance_dates) > 0
    assert rebalanced.total_turnover > 0


def test_contributions_increase_final_value_and_are_tracked():
    frame = _frame({"A": [0.0] * 24, "B": [0.0] * 24})
    result = simulate_portfolio(frame, [0.5, 0.5], initial_value=1000.0,
                                periodic_contribution=100.0, contribution_frequency="monthly",
                                transaction_cost_bps=0)
    # bdate_range over 24 business days spans 2 month-boundaries -> 2 contributions.
    assert result.total_contributions == 200.0
    assert result.final_value == pytest.approx(1200.0)


def test_transaction_costs_reduce_final_value():
    frame = _frame({"A": [0.02] * 30, "B": [0.01] * 30})
    free = simulate_portfolio(frame, [0.5, 0.5], rebalance_frequency="monthly",
                              transaction_cost_bps=0)
    costly = simulate_portfolio(frame, [0.5, 0.5], rebalance_frequency="monthly",
                                transaction_cost_bps=50)
    assert costly.total_costs > 0
    assert costly.final_value < free.final_value


def test_threshold_rebalancing_triggers_on_drift():
    frame = _frame({"A": [0.5] + [0.0] * 9, "B": [0.0] * 10})
    result = simulate_portfolio(frame, [0.5, 0.5], rebalance_frequency="threshold",
                                rebalance_threshold=0.05, transaction_cost_bps=0)
    assert result.total_turnover > 0


def test_weights_history_rows_sum_to_one():
    frame = _frame({"A": list(np.random.default_rng(2).normal(0, 0.01, 50)),
                    "B": list(np.random.default_rng(3).normal(0, 0.01, 50))})
    result = simulate_portfolio(frame, [0.6, 0.4], rebalance_frequency="quarterly")
    assert np.allclose(result.weights_history.sum(axis=1), 1.0)


def test_equity_curve_length_matches_input():
    frame = _frame({"A": [0.01] * 40})
    result = simulate_portfolio(frame, [1.0])
    assert len(result.equity) == 40
    assert len(result.dates) == 40
