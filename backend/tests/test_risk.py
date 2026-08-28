import math

import numpy as np
import pytest

from app.analytics import risk as RK


def test_annualized_volatility_scales_by_sqrt_of_periods():
    r = np.array([0.01, -0.01, 0.01, -0.01])
    daily_sd = np.std(r, ddof=1)
    assert RK.annualized_volatility(r, 252) == pytest.approx(daily_sd * math.sqrt(252))
    assert RK.annualized_volatility(r, 252) >= 0


def test_max_drawdown_is_non_positive(equity_curve):
    # 120 -> 60 is a 50% fall.
    assert RK.max_drawdown(equity_curve) == pytest.approx(-0.5)
    assert RK.max_drawdown(equity_curve) <= 0


def test_max_drawdown_of_monotonic_series_is_zero():
    assert RK.max_drawdown(np.array([1.0, 2.0, 3.0])) == pytest.approx(0.0)


def test_drawdown_series_never_positive(equity_curve):
    dd = RK.drawdown_series(equity_curve)
    assert np.all(dd <= 0)
    assert dd[0] == pytest.approx(0.0)


def test_recovery_periods(equity_curve):
    # Trough at index 2, back above 120 at index 4 -> 2 periods.
    assert RK.recovery_days(equity_curve) == 2


def test_recovery_periods_none_when_never_recovered():
    assert RK.recovery_days(np.array([100.0, 120.0, 60.0, 70.0])) is None


def test_drawdown_table_reports_dates(equity_curve):
    import pandas as pd

    dates = pd.bdate_range("2020-01-01", periods=len(equity_curve))
    table = RK.drawdown_table(equity_curve, dates)
    assert table
    assert table[0]["depth"] == pytest.approx(-0.5)
    assert table[0]["recovered"] is True


def test_downside_deviation():
    r = np.array([0.02, -0.03, 0.01, -0.02])
    expected = math.sqrt((0.0 + 0.03**2 + 0.0 + 0.02**2) / 4)
    assert RK.downside_deviation(r, mar=0.0, annualize=False) == pytest.approx(expected)


def test_sharpe_ratio_basic():
    assert RK.sharpe_ratio(0.12, 0.10, 0.05) == pytest.approx(0.7)


def test_sharpe_handles_zero_volatility():
    assert math.isnan(RK.sharpe_ratio(0.12, 0.0, 0.05))
    assert RK.sharpe_ratio(0.05, 0.0, 0.05) == 0.0


def test_sortino_handles_zero_downside_deviation():
    assert math.isnan(RK.sortino_ratio(0.12, 0.0, 0.05))
    assert RK.sortino_ratio(0.05, 0.0, 0.05) == 0.0


def test_calmar_ratio():
    assert RK.calmar_ratio(0.12, -0.30) == pytest.approx(0.4)
    assert math.isnan(RK.calmar_ratio(0.12, 0.0))


def test_historical_var_and_cvar():
    r = np.array([-0.05, -0.04, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06])
    # 95% VaR -> 5th percentile of returns ~ between -0.05 and -0.04
    var = RK.historical_var(r, 0.95)
    assert 0.04 <= var <= 0.05
    cvar = RK.historical_cvar(r, 0.95)
    assert cvar >= var  # expected shortfall is at least as bad as VaR


def test_parametric_var_matches_normal_quantile():
    from scipy import stats

    rng = np.random.default_rng(3)
    r = rng.normal(0.0, 0.01, 50_000)
    expected = -(float(np.mean(r)) + stats.norm.ppf(0.05) * np.std(r, ddof=1))
    assert RK.parametric_var(r, 0.95) == pytest.approx(expected, rel=1e-6)


def test_ulcer_index_penalises_duration():
    shallow_long = np.array([1.0] + [0.9] * 50)
    deep_short = np.array([1.0, 0.8, 1.0, 1.0, 1.0])
    assert RK.ulcer_index(shallow_long) > 0
    assert RK.ulcer_index(deep_short) > 0


def test_risk_summary_bundle(demo_universe_prices):
    from app.analytics import returns as R

    prices = demo_universe_prices["NIFTY50"].to_numpy()
    r = R.simple_returns(prices)[1:]
    summary = RK.risk_metrics_summary(r, 252, risk_free_rate=0.065)
    assert summary["observations"] == len(r)
    assert summary["volatility"] > 0
    assert summary["maxDrawdown"] <= 0
    assert summary["historicalVaR"] >= 0
    assert summary["historicalCVaR"] >= summary["historicalVaR"]
    assert not math.isnan(summary["sharpe"])
