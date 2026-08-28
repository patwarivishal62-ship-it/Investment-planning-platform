import numpy as np
import pandas as pd
import pytest

from app.analytics import correlation as C


def test_identical_series_have_correlation_one():
    idx = pd.bdate_range("2020-01-01", periods=50)
    s = pd.Series(np.linspace(1, 2, 50), index=idx)
    frame = pd.DataFrame({"a": s, "b": s})
    corr = C.pearson_correlation_matrix(frame)
    assert corr.loc["a", "b"] == pytest.approx(1.0)


def test_opposite_series_have_correlation_minus_one():
    idx = pd.bdate_range("2020-01-01", periods=50)
    a = pd.Series(np.linspace(1, 2, 50), index=idx)
    frame = pd.DataFrame({"a": a, "b": -a})
    corr = C.pearson_correlation_matrix(frame)
    assert corr.loc["a", "b"] == pytest.approx(-1.0)


def test_covariance_matrix_is_symmetric(two_asset_prices):
    from app.analytics import returns as R

    rets = R.returns_frame(two_asset_prices)
    cov = C.covariance_matrix(rets)
    assert cov.loc["EQ", "BOND"] == pytest.approx(cov.loc["BOND", "EQ"])
    assert cov.loc["EQ", "EQ"] > 0


def test_nearest_psd_fixes_negative_eigenvalue():
    bad = np.array([[1.0, 2.0], [2.0, 1.0]])
    fixed = C.nearest_psd(bad)
    eigenvalues = np.linalg.eigvalsh(fixed)
    assert np.all(eigenvalues > -1e-12)
    assert fixed[0, 1] == pytest.approx(fixed[1, 0])


def test_average_pairwise_correlation():
    corr = pd.DataFrame([[1.0, 0.4, 0.2], [0.4, 1.0, 0.0], [0.2, 0.0, 1.0]])
    assert C.average_pairwise_correlation(corr) == pytest.approx((0.4 + 0.2 + 0.0) / 3)


def test_rolling_correlation_has_expected_length(two_asset_prices):
    from app.analytics import returns as R

    rets = R.returns_frame(two_asset_prices)
    rolled = C.rolling_correlation(rets, "EQ", "BOND", window=20).dropna()
    assert len(rolled) == len(rets) - 20 + 1
    assert rolled.abs().max() <= 1.0 + 1e-9


def test_demo_universe_correlation_is_plausible(demo_universe_prices):
    from app.analytics import returns as R

    rets = R.returns_frame(demo_universe_prices)
    corr = C.pearson_correlation_matrix(rets)
    # Equities should be far more correlated with each other than with cash.
    assert corr.loc["NIFTY50", "NIFTYIT"] > 0.3
    assert abs(corr.loc["NIFTY50", "CASH"]) < 0.3
