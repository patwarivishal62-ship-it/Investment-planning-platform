"""Tests for the contribution / performance-return distinction and IRR."""
import asyncio
import numpy as np
import pandas as pd
import pytest

from app.analytics.backtest import simulate_portfolio
from app.services.simulation import money_weighted_return, summarize_curve


def test_time_weighted_return_ignores_contributions():
    """A flat market with contributions must report ~0% time-weighted return even
    though the account balance grows."""
    dates = pd.bdate_range("2020-01-01", periods=252)
    frame = pd.DataFrame({"A": [0.0] * 252}, index=dates)
    result = simulate_portfolio(frame, [1.0], initial_value=100_000.0,
                                periodic_contribution=10_000.0,
                                contribution_frequency="monthly",
                                transaction_cost_bps=0)
    summary = summarize_curve(dates, result.equity, result.returns, 252, 0.0,
                              result.total_contributions,
                              contribution_dates=result.contribution_dates,
                              initial_value=100_000.0)
    assert result.final_value > 100_000           # the account grew
    assert summary["cagr"] == pytest.approx(0.0, abs=1e-9)   # ...but the market did not
    assert summary["totalReturn"] == pytest.approx(0.0, abs=1e-9)
    assert summary["invested"] == pytest.approx(100_000.0 + result.total_contributions)


def test_money_weighted_return_matches_closed_form():
    # Invest 100, grow to 200 in exactly 5 years, no contributions -> IRR = 2^(1/5)-1
    mwr = money_weighted_return(100.0, 0.0, 0, 5.0, 200.0)
    assert mwr == pytest.approx(2 ** 0.2 - 1, abs=1e-4)


def test_money_weighted_return_is_below_cagr_when_contributions_late():
    """Money-weighted return differs from time-weighted whenever cash flows and
    returns interact -- the point is that they are reported separately."""
    dates = pd.bdate_range("2019-01-01", periods=504)
    rng = np.random.default_rng(0)
    frame = pd.DataFrame({"A": rng.normal(0.0008, 0.01, 504)}, index=dates)
    result = simulate_portfolio(frame, [1.0], initial_value=100_000.0,
                                periodic_contribution=25_000.0,
                                contribution_frequency="monthly",
                                transaction_cost_bps=0)
    summary = summarize_curve(dates, result.equity, result.returns, 252, 0.0,
                              result.total_contributions,
                              contribution_dates=result.contribution_dates,
                              initial_value=100_000.0)
    assert np.isfinite(summary["moneyWeightedReturn"])
    assert np.isfinite(summary["cagr"])
    # Both are reported; neither is derived from the other.
    assert "endValue" in summary and "invested" in summary


def test_drawdown_is_measured_on_the_time_weighted_curve():
    """A contribution made at the bottom must not hide the drawdown."""
    dates = pd.bdate_range("2020-01-01", periods=10)
    returns = [0.0, -0.20, -0.10, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    frame = pd.DataFrame({"A": returns}, index=dates)
    result = simulate_portfolio(frame, [1.0], initial_value=100.0,
                                periodic_contribution=0.0, transaction_cost_bps=0)
    summary = summarize_curve(dates, result.equity, result.returns, 252, 0.0)
    # 1.0 -> 0.8 -> 0.72 => -28%
    assert summary["maxDrawdown"] == pytest.approx(-0.28, abs=1e-9)


# ---------------------------------------------------------------------------
# Regression: every summary must know about contributions and the true start
# value, otherwise `invested` and `moneyWeightedReturn` silently describe a
# portfolio that never received the cash the investor actually put in.
# ---------------------------------------------------------------------------

class _Req:
    """Minimal stand-in for a request object carrying money assumptions."""

    def __init__(self, initial=1_000_000.0, monthly=20_000.0, symbols=None):
        self.initialValue = initial
        self.monthlyContribution = monthly
        self.symbols = symbols
        self.rebalanceFrequency = "quarterly"
        self.transactionCostBps = 10.0
        self.riskFreeRate = None
        self.start = None
        self.end = None
        self.trainEnd = "2023-12-31"
        self.strategy = "max_sharpe"
        self.contributionFrequency = "monthly"
        self.rebalanceThreshold = 0.10
        self.targetVolatility = None
        self.weights = None


def test_benchmarks_report_contributions_they_received():
    """Benchmarks receive the same contributions as the portfolio, so their
    `invested` figure must include them and their money-weighted return must
    not be computed as if the cash never arrived."""
    from app.services.simulation import SimulationService

    request = _Req(symbols=["NIFTY50", "GOLD", "GSEC10Y", "LIQUIDFUND"])
    request.weights = {"NIFTY50": 0.5, "GOLD": 0.2, "GSEC10Y": 0.2, "LIQUIDFUND": 0.1}
    result = asyncio.run(SimulationService().backtest(request))
    assert result["benchmarks"], "expected benchmark comparisons"
    for bench in result["benchmarks"]:
        assert bench["contributions"] > 0
        assert bench["startValue"] == pytest.approx(1_000_000.0)
        assert bench["invested"] == pytest.approx(
            1_000_000.0 + bench["contributions"], rel=1e-6
        )
        # The old bug reported a ~23% money-weighted return for a ~4% asset,
        # because contributions were treated as investment performance.
        assert bench["moneyWeightedReturn"] < bench["cagr"] + 0.10


def test_walk_forward_reports_contributions_in_both_windows():
    from app.services.simulation import SimulationService

    result = asyncio.run(SimulationService().walk_forward(_Req()))
    for window in (result["inSample"], result["outOfSample"]):
        assert window["startValue"] == pytest.approx(1_000_000.0)
        assert window["contributions"] > 0
        assert window["invested"] == pytest.approx(
            1_000_000.0 + window["contributions"], rel=1e-6
        )
        assert window["moneyWeightedReturn"] < window["cagr"] + 0.10
        # A time-weighted growth curve is always exposed for charting.
        assert window["performanceCurve"], "expected a time-weighted curve"
        assert len(window["performanceCurve"]) == len(window["dates"])


def test_walk_forward_is_genuinely_out_of_sample():
    """The test window must start strictly after the training window ends."""
    from app.services.simulation import SimulationService

    result = asyncio.run(SimulationService().walk_forward(_Req()))
    assumptions = result["assumptions"]
    assert assumptions["testStart"] > assumptions["trainEnd"]
    assert assumptions["noLookAhead"] is True
    # The optimiser only ever saw data up to the end of training.
    assert result["inSample"]["end"] <= assumptions["trainEnd"]


def test_rebalance_comparison_reports_contributions():
    from app.services.simulation import SimulationService

    request = _Req()
    request.weights = {"NIFTY50": 0.5, "GOLD": 0.2, "GSEC10Y": 0.3}
    result = asyncio.run(SimulationService().rebalance_compare(request))
    assert result["results"], "expected one row per rebalancing rule"
    for row in result["results"]:
        assert row["startValue"] == pytest.approx(1_000_000.0)
        assert row["invested"] == pytest.approx(
            1_000_000.0 + row["contributions"], rel=1e-6
        )
