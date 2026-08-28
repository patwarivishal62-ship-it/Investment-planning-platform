"""Efficient frontier: minimum achievable volatility for each target return."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from .constraints import ConstraintSet, OptimizationError, build_constraint_set, project_to_bounds

__all__ = ["efficient_frontier", "frontier_point"]


def frontier_point(
    target_return: float,
    mu: np.ndarray,
    cov: np.ndarray,
    cs: ConstraintSet,
    x0: np.ndarray | None = None,
) -> dict | None:
    """Minimum-variance portfolio that achieves exactly ``target_return``."""
    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)
    cons = [
        {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0), "jac": lambda w: np.ones_like(w)},
        {"type": "eq", "fun": lambda w: float(w @ mu) - float(target_return), "jac": lambda w: mu},
    ]
    if cs.a_ub is not None and cs.b_ub is not None:
        cons.append({"type": "ineq", "fun": lambda w: cs.b_ub - cs.a_ub @ w, "jac": lambda w: -cs.a_ub})
    start = x0 if x0 is not None else cs.feasible_point()
    if start is None:
        return None
    res = minimize(
        lambda w: float(w @ cov @ w),
        start,
        jac=lambda w: 2.0 * cov @ w,
        method="SLSQP",
        bounds=cs.as_bounds(),
        constraints=cons,
        options={"maxiter": 400, "ftol": 1e-12},
    )
    if not res.success:
        return None
    w = project_to_bounds(np.clip(res.x, 0.0, None) / np.clip(np.sum(np.clip(res.x, 0.0, None)), 1e-12, None), cs.lower, cs.upper)
    if w is None:
        return None
    if cs.a_ub is not None and np.any(cs.a_ub @ w - cs.b_ub > 1e-5):
        return None
    if abs(float(w @ mu) - target_return) > 5e-3:
        return None
    return {
        "targetReturn": float(target_return),
        "expectedReturn": float(w @ mu),
        "volatility": float(np.sqrt(max(w @ cov @ w, 0.0))),
        "weights": w,
    }


def efficient_frontier(
    mu: np.ndarray,
    cov: np.ndarray,
    symbols: list[str],
    constraints,
    class_of: dict[str, str] | None = None,
    sector_of: dict[str, str] | None = None,
    points: int = 40,
    risk_free_rate: float = 0.0,
) -> dict:
    """Compute the constrained frontier between min-variance and max-return."""
    from .optimizers import OptimizationInput, min_variance

    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)
    cs = build_constraint_set(symbols, constraints, class_of, sector_of)

    lo = min_variance(OptimizationInput(mu=mu, cov=cov, symbols=symbols, constraints=constraints,
                                        class_of=class_of, sector_of=sector_of,
                                        risk_free_rate=risk_free_rate))
    lo_ret = float(lo["weights"] @ mu)
    hi_ret = float(np.max(mu[cs.upper > 1e-9])) if np.any(cs.upper > 1e-9) else lo_ret

    grid = np.linspace(lo_ret, hi_ret, max(2, int(points)))
    curve: list[dict] = []
    x0 = lo["weights"]
    for target in grid:
        point = frontier_point(float(target), mu, cov, cs, x0=x0)
        if point is None:
            continue
        x0 = point["weights"]
        curve.append(point)

    # Tangency (max Sharpe) point on the computed frontier.
    tangency = None
    if curve:
        best = max(curve, key=lambda p: (p["expectedReturn"] - risk_free_rate) / p["volatility"] if p["volatility"] > 0 else -np.inf)
        tangency = {"expectedReturn": best["expectedReturn"], "volatility": best["volatility"]}

    return {
        "points": [
            {"expectedReturn": p["expectedReturn"], "volatility": p["volatility"]}
            for p in curve
        ],
        "minVariance": {"expectedReturn": lo_ret, "volatility": float(lo["volatility"])},
        "maxReturn": {"expectedReturn": float(hi_ret), "volatility": None},
        "tangency": tangency,
        "riskFreeRate": float(risk_free_rate),
    }
