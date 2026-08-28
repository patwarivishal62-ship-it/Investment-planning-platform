import math

import numpy as np
import pytest

from app.analytics import returns as R
from app.analytics import statistics as S


def test_simple_returns(simple_prices):
    r = R.simple_returns(simple_prices)
    assert np.isnan(r[0])
    assert r[1] == pytest.approx(0.10)
    assert r[2] == pytest.approx(-0.10)
    assert r[3] == pytest.approx(0.10)


def test_log_returns(simple_prices):
    r = R.log_returns(simple_prices)
    assert np.isnan(r[0])
    assert r[1] == pytest.approx(math.log(1.10))
    assert r[2] == pytest.approx(math.log(0.90))


def test_negative_prices_rejected():
    with pytest.raises(ValueError):
        R.simple_returns(np.array([100.0, -5.0, 110.0]))
    with pytest.raises(ValueError):
        R.simple_returns(np.array([100.0, 0.0, 110.0]))


def test_cumulative_return(simple_returns_series):
    # 1.1 * 0.9 * 1.1 - 1 = 0.089
    assert R.cumulative_return(simple_returns_series) == pytest.approx(0.089)


def test_annualized_arithmetic_vs_geometric():
    r = np.array([0.01] * 252)
    assert R.annualized_return(r, 252, "arithmetic") == pytest.approx(2.52)
    # (1.01)^252 - 1
    assert R.annualized_return(r, 252, "geometric") == pytest.approx(1.01**252 - 1)


def test_cagr_basic():
    assert R.cagr(1_000_000, 2_000_000, 10) == pytest.approx(2 ** (0.1) - 1)


def test_cagr_invalid_periods_are_nan():
    assert math.isnan(R.cagr(100, 200, 0))
    assert math.isnan(R.cagr(100, 200, -3))
    assert math.isnan(R.cagr(0, 200, 5))
    assert math.isnan(R.cagr(100, float("nan"), 5))


def test_returns_frame_drops_first_row(two_asset_prices):
    frame = R.returns_frame(two_asset_prices)
    assert len(frame) == len(two_asset_prices) - 1
    assert not frame.isna().any().any()


def test_descriptive_statistics_known_values():
    data = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    assert S.mean(data) == pytest.approx(22.0)
    assert S.median(data) == pytest.approx(3.0)
    # numpy var with ddof=1
    assert S.variance(data) == pytest.approx(np.var(data, ddof=1))
    assert S.std_dev(data) == pytest.approx(np.std(data, ddof=1))
    assert S.minimum(data) == pytest.approx(1.0)
    assert S.maximum(data) == pytest.approx(100.0)
    # Heavily right-skewed data must have positive skew and excess kurtosis.
    assert S.skewness(data) > 0
    assert S.kurtosis(data) > 0


def test_skewness_of_symmetric_data_is_zero():
    data = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    assert S.skewness(data) == pytest.approx(0.0, abs=1e-12)


def test_statistics_handle_empty_and_nan():
    assert math.isnan(S.mean(np.array([])))
    assert math.isnan(S.std_dev(np.array([np.nan, np.nan])))
    assert math.isnan(S.skewness(np.array([1.0, 2.0])))


def test_normal_distribution_has_zero_excess_kurtosis():
    rng = np.random.default_rng(0)
    data = rng.normal(0, 1, 200_000)
    assert S.kurtosis(data) == pytest.approx(0.0, abs=0.05)
    assert S.skewness(data) == pytest.approx(0.0, abs=0.05)
