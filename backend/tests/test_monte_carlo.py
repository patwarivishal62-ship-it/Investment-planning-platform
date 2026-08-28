import numpy as np
import pytest

from app.analytics.monte_carlo import monte_carlo


def test_monte_carlo_is_reproducible_with_a_seed():
    kwargs = dict(
        weights=[0.6, 0.4],
        mu_annual=np.array([0.12, 0.06]),
        cov_annual=np.array([[0.04, 0.005], [0.005, 0.01]]),
        initial_value=1_000_000,
        periodic_contribution=10_000,
        years=5,
        paths=500,
        seed=7,
    )
    a = monte_carlo(**kwargs)
    b = monte_carlo(**kwargs)
    assert a["finalValues"] == b["finalValues"]
    assert a["percentilePaths"]["p50"] == b["percentilePaths"]["p50"]


def test_different_seeds_produce_different_paths():
    base = dict(weights=[1.0], mu_annual=np.array([0.1]), cov_annual=np.array([[0.04]]),
                initial_value=1000, years=3, paths=300)
    a = monte_carlo(seed=1, **base)
    b = monte_carlo(seed=2, **base)
    assert a["medianFinalValue"] != b["medianFinalValue"]


def test_zero_volatility_is_deterministic():
    result = monte_carlo(
        weights=[1.0],
        mu_annual=np.array([0.12]),
        cov_annual=np.array([[0.0]]),
        initial_value=1000.0,
        years=2,
        paths=200,
        seed=3,
    )
    # 12% p.a. compounded monthly for 2 years, no volatility, no contributions.
    expected = 1000.0 * (1 + 0.12 / 12) ** 24
    assert result["medianFinalValue"] == pytest.approx(expected, rel=1e-9)
    for key in ("p10", "p25", "p50", "p75", "p90"):
        assert result["finalValues"][key] == pytest.approx(expected, rel=1e-9)


def test_percentiles_are_ordered():
    result = monte_carlo(
        weights=[0.5, 0.5], mu_annual=np.array([0.1, 0.05]),
        cov_annual=np.array([[0.04, 0.01], [0.01, 0.02]]),
        initial_value=500_000, years=10, paths=2000, seed=11,
    )
    values = [result["finalValues"][k] for k in ("p10", "p25", "p50", "p75", "p90")]
    assert all(b >= a for a, b in zip(values, values[1:]))
    assert 0.0 <= result["probabilityOfLoss"] <= 1.0


def test_bootstrap_uses_historical_returns():
    rng = np.random.default_rng(5)
    hist = rng.normal(0.0005, 0.01, 1200)
    result = monte_carlo(
        weights=[1.0], mu_annual=np.array([0.1]), cov_annual=np.array([[0.04]]),
        initial_value=100_000, years=5, paths=500, seed=4, method="bootstrap",
        historical_returns=hist,
    )
    assert result["method"] == "bootstrap"
    assert result["medianFinalValue"] > 0


def test_bootstrap_without_history_raises():
    with pytest.raises(ValueError):
        monte_carlo(weights=[1.0], mu_annual=np.array([0.1]), cov_annual=np.array([[0.04]]),
                    initial_value=1000, method="bootstrap")


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        monte_carlo(weights=[1.0], mu_annual=np.array([0.1]), cov_annual=np.array([[0.04]]),
                    initial_value=1000, method="magic")


def test_percentile_paths_have_expected_length():
    result = monte_carlo(
        weights=[1.0], mu_annual=np.array([0.08]), cov_annual=np.array([[0.02]]),
        initial_value=1000, years=3, paths=100, seed=9, steps_per_year=12,
    )
    assert len(result["yearsAxis"]) == 37
    assert len(result["percentilePaths"]["p50"]) == 37
