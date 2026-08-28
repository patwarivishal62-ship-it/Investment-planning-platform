import math

import numpy as np
import pytest

from app.analytics import portfolio as PF
from app.analytics import portfolio as pf


def test_normalize_weights_sums_to_one():
    w = PF.normalize_weights([2, 3, 5])
    assert w.sum() == pytest.approx(1.0)
    assert w[2] == pytest.approx(0.5)


def test_negative_weights_rejected():
    with pytest.raises(ValueError):
        PF.normalize_weights([0.5, -0.1, 0.6])


def test_portfolio_expected_return_is_linear():
    assert PF.portfolio_expected_return([0.5, 0.5], [0.10, 0.04]) == pytest.approx(0.07)


def test_portfolio_variance_known_value(diagonal_cov):
    # 0.5^2 * 0.04 + 0.5^2 * 0.01 = 0.0125
    assert PF.portfolio_variance([0.5, 0.5], diagonal_cov) == pytest.approx(0.0125)
    assert PF.portfolio_volatility([0.5, 0.5], diagonal_cov) == pytest.approx(math.sqrt(0.0125))


def test_portfolio_variance_is_never_negative():
    # A deliberately non-PSD matrix must not produce a negative variance.
    bad = np.array([[0.04, 0.09], [0.09, 0.04]])
    assert PF.portfolio_variance([0.5, 0.5], bad) >= 0.0


def test_diversified_portfolio_has_lower_vol_than_weighted_average():
    corr = 0.2
    cov = np.array([[0.04, corr * 0.2 * 0.1], [corr * 0.2 * 0.1, 0.01]])
    vol = PF.portfolio_volatility([0.5, 0.5], cov)
    assert vol < 0.5 * 0.2 + 0.5 * 0.1


def test_risk_contribution_sums_to_portfolio_volatility(diagonal_cov):
    result = PF.risk_contribution([0.5, 0.5], diagonal_cov, ["A", "B"])
    total = sum(c["riskContribution"] for c in result["contributions"])
    assert total == pytest.approx(result["portfolioVolatility"])
    assert sum(c["riskShare"] for c in result["contributions"]) == pytest.approx(1.0)


def test_risk_contribution_shares_for_diagonal_cov(diagonal_cov):
    # var contributions: 0.25*0.04 = 0.01 and 0.25*0.01 = 0.0025 -> 80% / 20%
    result = PF.risk_contribution([0.5, 0.5], diagonal_cov, ["A", "B"])
    shares = {c["symbol"]: c["riskShare"] for c in result["contributions"]}
    assert shares["A"] == pytest.approx(0.8)
    assert shares["B"] == pytest.approx(0.2)


def test_diversification_ratio(diagonal_cov):
    dr = PF.diversification_ratio([0.5, 0.5], [0.2, 0.1], diagonal_cov)
    assert dr > 1.0  # diversification reduces risk vs the weighted average


def test_effective_n_and_hhi():
    assert PF.herfindahl_index([0.25] * 4) == pytest.approx(0.25)
    assert PF.effective_n([0.25] * 4) == pytest.approx(4.0)
    assert PF.effective_n([1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_asset_class_exposure():
    exposure = PF.asset_class_exposure(
        [0.5, 0.3, 0.2], ["A", "B", "C"], {"A": "equity", "B": "equity", "C": "bond"}
    )
    assert exposure["equity"] == pytest.approx(0.8)
    assert exposure["bond"] == pytest.approx(0.2)


def test_portfolio_returns_matrix_matches_manual():
    r = np.array([[0.01, 0.02], [-0.01, 0.005]])
    out = PF.portfolio_returns(r, [0.5, 0.5])
    assert out[0] == pytest.approx(0.015)
    assert out[1] == pytest.approx(-0.0025)


def test_consolidate_weights_drops_tiny_holdings():
    w = pf.consolidate_weights([0.5, 0.005, 0.495], min_weight=0.02)
    assert w[1] == 0.0
    assert w.sum() == pytest.approx(1.0)
    assert w[0] == pytest.approx(0.5 / 0.995)


def test_consolidate_is_a_no_op_when_above_threshold():
    w = pf.consolidate_weights([0.6, 0.4], min_weight=0.02)
    assert np.allclose(w, [0.6, 0.4])


def test_consolidate_respects_class_upper_bounds():
    """Dropping a small equity sleeve would lift equity from 52% to 56.5% of the
    survivors, breaching a 55% cap -- so the original weights must be kept."""
    class_of = {"A": "equity", "B": "equity", "C": "bond"}
    w = pf.consolidate_weights([0.52, 0.08, 0.40], min_weight=0.20,
                               class_of=class_of, class_bounds={"equity": (0.0, 0.55)})
    assert np.allclose(w, [0.52, 0.08, 0.40])


def test_consolidate_allows_trim_that_stays_within_bounds():
    class_of = {"A": "equity", "B": "equity", "C": "bond"}
    w = pf.consolidate_weights([0.52, 0.08, 0.40], min_weight=0.20,
                               class_of=class_of, class_bounds={"equity": (0.0, 0.60)})
    assert w[1] == 0.0
    assert w.sum() == pytest.approx(1.0)
    assert w[0] == pytest.approx(0.52 / 0.92)
