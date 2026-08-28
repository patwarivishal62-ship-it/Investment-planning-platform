import math

import numpy as np
import pytest

from app.optimization.candidates import generate_candidates, screen_candidates, select_diverse
from app.optimization.constraints import OptimizationConstraints, build_constraint_set
from app.optimization.diagnostics import feasibility_report
from app.optimization.optimizers import OptimizationInput, optimize
from app.optimization.frontier import efficient_frontier


def _input(mu, cov, symbols, constraints, **kw):
    return OptimizationInput(mu=mu, cov=cov, symbols=symbols, constraints=constraints, **kw)


def test_min_variance_matches_closed_form(diagonal_cov, diagonal_mu):
    """For a zero-correlation 2-asset case the minimum-variance weights are
    proportional to 1/sigma^2: w_A = 0.01/(0.01+0.04) = 0.2, w_B = 0.8."""
    out = optimize(
        "min_variance",
        _input(diagonal_mu, diagonal_cov, ["A", "B"], OptimizationConstraints()),
    )
    assert out["weights"].sum() == pytest.approx(1.0)
    assert out["weights"][0] == pytest.approx(0.2, abs=1e-3)
    assert out["weights"][1] == pytest.approx(0.8, abs=1e-3)
    assert out["volatility"] == pytest.approx(math.sqrt(0.008), abs=1e-4)


def test_max_sharpe_prefers_high_risk_adjusted_asset(diagonal_cov, diagonal_mu):
    cov = np.array([[0.01, 0.0], [0.0, 0.01]])
    mu = np.array([0.15, 0.05])
    out = optimize("max_sharpe", _input(mu, cov, ["A", "B"], OptimizationConstraints(), risk_free_rate=0.05))
    assert out["weights"][0] == pytest.approx(1.0, abs=1e-3)


def test_all_strategies_respect_weight_bounds(diagonal_cov, diagonal_mu):
    constraints = OptimizationConstraints(min_weight=0.2, max_weight=0.6)
    for strategy in ("min_variance", "max_sharpe", "risk_parity", "max_diversification"):
        out = optimize(strategy, _input(diagonal_mu, diagonal_cov, ["A", "B"], constraints))
        w = out["weights"]
        assert w.sum() == pytest.approx(1.0)
        assert np.all(w >= 0.2 - 1e-6)
        assert np.all(w <= 0.6 + 1e-6)


def test_max_return_for_risk_respects_volatility_cap(diagonal_cov, diagonal_mu):
    out = optimize(
        "max_return_for_risk",
        _input(diagonal_mu, diagonal_cov, ["A", "B"], OptimizationConstraints(), target_volatility=0.12),
    )
    assert out["volatility"] <= 0.12 + 1e-4


def test_risk_parity_equalises_risk_shares_for_diagonal_cov():
    cov = np.array([[0.04, 0.0], [0.0, 0.01]])
    out = optimize("risk_parity", OptimizationInput(
        mu=np.array([0.1, 0.05]), cov=cov, symbols=["A", "B"],
        constraints=OptimizationConstraints(max_weight=1.0),
    ))
    shares = out["riskShares"]
    assert shares[0] == pytest.approx(0.5, abs=1e-3)
    assert shares[1] == pytest.approx(0.5, abs=1e-3)
    # Equal risk with vol ratio 2:1 -> capital weights 1:2
    assert out["weights"][0] == pytest.approx(1 / 3, abs=1e-3)
    assert out["weights"][1] == pytest.approx(2 / 3, abs=1e-3)


def test_class_constraints_are_enforced():
    cov = np.array([[0.04, 0.0, 0.0], [0.0, 0.09, 0.0], [0.0, 0.0, 0.01]])
    mu = np.array([0.30, 0.40, 0.05])
    constraints = OptimizationConstraints(class_bounds={"equity": (0.0, 0.5)})
    out = optimize(
        "max_sharpe",
        OptimizationInput(mu=mu, cov=cov, symbols=["A", "B", "C"],
                          constraints=constraints,
                          class_of={"A": "equity", "B": "equity", "C": "bond"}),
    )
    equity = out["weights"][0] + out["weights"][1]
    assert equity <= 0.5 + 1e-4


def test_min_cvar_reduces_tail_loss(demo_universe_prices):
    from app.analytics import returns as R

    rets = R.returns_frame(demo_universe_prices)
    rets = rets.drop(columns=["CASH"])
    symbols = list(rets.columns)
    mu = (rets.mean() * 252).to_numpy()
    cov = (rets.cov() * 252).to_numpy()
    constraints = OptimizationConstraints(max_weight=0.6)
    out = optimize(
        "min_cvar",
        OptimizationInput(mu=mu, cov=cov, symbols=symbols, constraints=constraints,
                          returns_matrix=rets.to_numpy()),
    )
    assert out["weights"].sum() == pytest.approx(1.0)
    equal = np.full(len(symbols), 1 / len(symbols))
    port_cvar = rets.to_numpy() @ out["weights"]
    port_equal = rets.to_numpy() @ equal
    k = int(len(port_cvar) * 0.05)
    assert -np.mean(np.sort(port_cvar)[:k]) <= -np.mean(np.sort(port_equal)[:k]) + 1e-6


def test_candidate_generation_respects_bounds():
    symbols = ["A", "B", "C", "D"]
    constraints = OptimizationConstraints(max_weight=0.5, min_weight=0.05)
    w = generate_candidates(symbols, constraints, count=200, seed=11)
    assert w.shape[0] == 200
    assert np.all(w >= 0.05 - 1e-6)
    assert np.all(w <= 0.5 + 1e-6)
    assert np.allclose(w.sum(axis=1), 1.0)


def test_candidate_generation_is_deterministic():
    symbols = ["A", "B", "C", "D"]
    constraints = OptimizationConstraints(max_weight=0.6)
    a = generate_candidates(symbols, constraints, count=50, seed=99)
    b = generate_candidates(symbols, constraints, count=50, seed=99)
    assert np.allclose(a, b)


def test_screen_candidates_filters_on_volatility():
    weights = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    mu = np.array([0.20, 0.05])
    cov = np.array([[0.09, 0.0], [0.0, 0.01]])
    pool = screen_candidates(weights, mu, cov, max_volatility=0.2)
    assert len(pool) == 2
    assert pool.volatility.max() <= 0.2 + 1e-9


def test_select_diverse_returns_distinct_portfolios():
    weights = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.99, 0.01, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.34, 0.33, 0.33],
        ]
    )
    chosen = select_diverse(weights, np.array([1.0, 0.9, 0.8, 0.7, 0.6]), limit=3, min_distance=0.5)
    assert len(chosen) == 3
    for i in range(len(chosen)):
        for j in range(i + 1, len(chosen)):
            assert np.abs(weights[chosen[i]] - weights[chosen[j]]).sum() >= 0.5 - 1e-9


def test_efficient_frontier_is_monotonic(diagonal_cov, diagonal_mu):
    result = efficient_frontier(
        diagonal_mu, diagonal_cov, ["A", "B"], OptimizationConstraints(), points=12
    )
    points = result["points"]
    assert len(points) >= 2
    returns_ = [p["expectedReturn"] for p in points]
    assert all(b >= a - 1e-9 for a, b in zip(returns_, returns_[1:]))
    assert result["minVariance"]["volatility"] <= min(p["volatility"] for p in points) + 1e-9


def test_infeasible_volatility_cap_is_diagnosed(diagonal_cov, diagonal_mu):
    report = feasibility_report(
        diagonal_mu, diagonal_cov, ["A", "B"],
        OptimizationConstraints(max_volatility=0.02),
    )
    assert report["feasible"] is False
    assert any("Increase the maximum volatility" in s for s in report["suggestions"])
    # Analytic minimum: w = (0.2, 0.8) -> variance 0.008 -> vol 8.94%
    assert report["minVolatility"] == pytest.approx(math.sqrt(0.008), abs=1e-3)


def test_conflicting_class_bounds_are_diagnosed():
    cov = np.eye(3) * 0.04
    mu = np.array([0.1, 0.1, 0.1])
    report = feasibility_report(
        mu, cov, ["A", "B", "C"],
        OptimizationConstraints(class_bounds={"equity": (0.8, None), "bond": (0.5, None)}),
        class_of={"A": "equity", "B": "equity", "C": "bond"},
    )
    assert report["linearFeasible"] is False
    assert report["suggestions"]
