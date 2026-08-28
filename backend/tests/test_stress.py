import numpy as np
import pandas as pd
import pytest

from app.analytics.stress import (
    SCENARIOS,
    apply_scenario,
    historical_stress_windows,
    replay_window,
)


CLASS_OF = {"EQ": "equity", "GOLD": "gold", "BOND": "bond", "CASH": "cash"}


def test_equity_crash_impacts_equity_only_portfolio():
    result = apply_scenario([1.0, 0, 0, 0], ["EQ", "GOLD", "BOND", "CASH"], CLASS_OF,
                            SCENARIOS["equity_crash"]["shocks"], value=1_000_000)
    assert result["portfolioImpact"] == pytest.approx(-0.30)
    assert result["valueAfter"] == pytest.approx(700_000)


def test_diversified_portfolio_absorbs_less_of_the_shock():
    weights = [0.5, 0.2, 0.2, 0.1]
    result = apply_scenario(weights, ["EQ", "GOLD", "BOND", "CASH"], CLASS_OF,
                            SCENARIOS["equity_crash"]["shocks"], value=1_000_000)
    assert result["portfolioImpact"] > -0.30
    assert result["portfolioImpact"] == pytest.approx(
        0.5 * -0.30 + 0.2 * 0.05 + 0.2 * 0.02 + 0.1 * 0.0
    )


def test_symbol_level_shock_overrides_class_level():
    shocks = [
        {"scope": "assetClass", "target": "equity", "shock": -0.30},
        {"scope": "symbol", "target": "EQ", "shock": -0.50},
    ]
    result = apply_scenario([1.0, 0, 0, 0], ["EQ", "GOLD", "BOND", "CASH"], CLASS_OF, shocks)
    assert result["portfolioImpact"] == pytest.approx(-0.50)


def test_custom_scenario_is_editable():
    shocks = [{"scope": "assetClass", "target": "gold", "shock": -0.25}]
    result = apply_scenario([0, 1.0, 0, 0], ["EQ", "GOLD", "BOND", "CASH"], CLASS_OF, shocks)
    assert result["portfolioImpact"] == pytest.approx(-0.25)


def test_historical_windows_are_ordered_worst_first():
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.0004, 0.01, 800),
                        index=pd.bdate_range("2018-01-01", periods=800))
    windows = historical_stress_windows(returns, window_days=60, top=3)
    assert len(windows) == 3
    assert all(b["return"] >= a["return"] for a, b in zip(windows, windows[1:]))
    assert windows[0]["return"] < 0


def test_replay_window_uses_only_the_selected_period():
    rng = np.random.default_rng(1)
    returns = pd.DataFrame({"A": rng.normal(0.001, 0.01, 500),
                            "B": rng.normal(0.0005, 0.005, 500)},
                           index=pd.bdate_range("2019-01-01", periods=500))
    result = replay_window([0.5, 0.5], returns, "2019-06-01", "2019-12-31")
    assert result["basis"] == "observed"
    assert result["start"] == "2019-06-03"
    assert len(result["equityCurve"]) == len(result["dates"])
    assert result["maxDrawdown"] <= 0
