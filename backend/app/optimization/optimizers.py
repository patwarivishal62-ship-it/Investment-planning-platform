"""Six optimization strategies, all solved with SLSQP over the same constraints.

    1. min_variance               min   w'Sigma w
    2. max_sharpe                 max   (mu'w - rf) / sqrt(w'Sigma w)
    3. max_return_for_risk        max   mu'w   s.t. sqrt(w'Sigma w) <= v*
    4. risk_parity                min   sum_i (RC_i - sigma_p/N)^2
    5. max_diversification        max   (w.sigma_i) / sqrt(w'Sigma w)
    6. min_cvar                   min   ES_alpha(w'R)  s.t. mu'w >= target

Every strategy returns a dict with the weights plus the achieved objective so
callers can compare them. Failures raise OptimizationError with an explanation;
they never fall back to a portfolio that violates constraints.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .constraints import (
    ConstraintSet,
    OptimizationError,
    build_constraint_set,
    project_to_bounds,
)

__all__ = [
    "OptimizationInput",
    "optimize",
    "min_variance",
    "max_sharpe",
    "max_return_for_risk",
    "risk_parity",
    "max_diversification",
    "min_cvar",
    "STRATEGIES",
]

STRATEGIES = (
    "min_variance",
    "max_sharpe",
    "max_return_for_risk",
    "risk_parity",
    "max_diversification",
    "min_cvar",
)


@dataclass
class OptimizationInput:
    mu: np.ndarray                # annualized expected returns, length N
    cov: np.ndarray               # annualized covariance, N x N
    symbols: list[str]
    constraints: object           # OptimizationConstraints
    class_of: dict[str, str] | None = None
    sector_of: dict[str, str] | None = None
    risk_free_rate: float = 0.0
    returns_matrix: np.ndarray | None = None  # T x N periodic returns, for CVaR
    cvar_alpha: float = 0.95
    target_volatility: float | None = None
    target_return: float | None = None


def _slsqp(
    fun,
    x0: np.ndarray,
    cs: ConstraintSet,
    jac=None,
    extra=(),
    maxiter: int = 400,
    ftol: float = 1e-12,
):
    """SLSQP over sum(w)=1, the weight box and the group-limit polytope."""
    cons = [
        {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0), "jac": lambda w: np.ones_like(w)},
    ]
    if cs.a_ub is not None and cs.b_ub is not None:
        cons.append({"type": "ineq", "fun": lambda w: cs.b_ub - cs.a_ub @ w, "jac": lambda w: -cs.a_ub})
    cons.extend(extra)
    return minimize(
        fun,
        x0,
        jac=jac,
        method="SLSQP",
        bounds=cs.as_bounds(),
        constraints=cons,
        options={"maxiter": maxiter, "ftol": ftol, "disp": False},
    )


def _finalize(res, cs: ConstraintSet, name: str) -> np.ndarray:
    if not res.success:
        raise OptimizationError(
            f"{name} optimization did not converge: {res.message}",
            suggestions=["Relax allocation constraints and retry."],
            detail={"method": name},
        )
    w = np.clip(np.asarray(res.x, dtype=float), 0.0, None)
    total = float(w.sum())
    if total <= 0:
        raise OptimizationError(f"{name} optimization returned an empty portfolio")
    w = w / total
    # Re-project onto the bounds: SLSQP can leave ~1e-9 violations.
    projected = project_to_bounds(w, cs.lower, cs.upper)
    if projected is None:
        raise OptimizationError(f"{name} result could not be projected onto the weight bounds")
    problems = cs.violations(projected, tol=1e-4)
    if problems:
        raise OptimizationError(
            f"{name} result violates constraints: {'; '.join(problems)}",
            detail={"method": name},
        )
    return projected


def _start(cs: ConstraintSet, mu: np.ndarray | None = None) -> np.ndarray:
    x0 = cs.feasible_point()
    if x0 is None:
        raise OptimizationError(
            "No starting portfolio satisfies the per-asset weight bounds",
            suggestions=[
                "Widen the maximum single-asset allocation, or reduce the number of "
                "mandatory minimum weights."
            ],
        )
    return x0


# ------------------------------------------------------------------ strategy 1


def min_variance(inp: OptimizationInput) -> dict:
    cs = build_constraint_set(inp.symbols, inp.constraints, inp.class_of, inp.sector_of)
    cov = np.asarray(inp.cov, dtype=float)

    def objective(w):
        return float(w @ cov @ w)

    def gradient(w):
        return 2.0 * cov @ w

    res = _slsqp(objective, _start(cs), cs, jac=gradient, maxiter=500)
    w = _finalize(res, cs, "Minimum variance")
    return {"weights": w, "volatility": float(np.sqrt(max(objective(w), 0.0))), "expectedReturn": float(w @ inp.mu), "method": "min_variance"}


# ------------------------------------------------------------------ strategy 2


def max_sharpe(inp: OptimizationInput) -> dict:
    cs = build_constraint_set(inp.symbols, inp.constraints, inp.class_of, inp.sector_of)
    cov = np.asarray(inp.cov, dtype=float)
    mu = np.asarray(inp.mu, dtype=float)
    rf = float(inp.risk_free_rate)

    def neg_sharpe(w):
        sigma = float(np.sqrt(max(w @ cov @ w, 1e-18)))
        return -((float(w @ mu) - rf) / sigma)

    res = _slsqp(neg_sharpe, _start(cs), cs, maxiter=600)
    w = _finalize(res, cs, "Maximum Sharpe")
    sigma = float(np.sqrt(max(w @ cov @ w, 0.0)))
    return {
        "weights": w,
        "volatility": sigma,
        "expectedReturn": float(w @ mu),
        "sharpe": float("nan") if sigma <= 0 else float((float(w @ mu) - rf) / sigma),
        "method": "max_sharpe",
    }


# ------------------------------------------------------------------ strategy 3


def max_return_for_risk(inp: OptimizationInput) -> dict:
    cs = build_constraint_set(inp.symbols, inp.constraints, inp.class_of, inp.sector_of)
    cov = np.asarray(inp.cov, dtype=float)
    mu = np.asarray(inp.mu, dtype=float)
    target_vol = inp.target_volatility
    if target_vol is None:
        target_vol = float(getattr(inp.constraints, "max_volatility", None) or 0.15)

    extra = [
        {
            "type": "ineq",
            "fun": lambda w: float(target_vol**2 - (w @ cov @ w)),
            "jac": lambda w: -2.0 * cov @ w,
        }
    ]
    res = _slsqp(lambda w: float(-(w @ mu)), _start(cs), cs, jac=lambda w: -mu, extra=extra, maxiter=500)
    w = _finalize(res, cs, "Maximum return under risk constraint")
    sigma = float(np.sqrt(max(w @ cov @ w, 0.0)))
    return {
        "weights": w,
        "volatility": sigma,
        "expectedReturn": float(w @ mu),
        "targetVolatility": float(target_vol),
        "method": "max_return_for_risk",
    }


# ------------------------------------------------------------------ strategy 4


def risk_parity(inp: OptimizationInput) -> dict:
    cs = build_constraint_set(inp.symbols, inp.constraints, inp.class_of, inp.sector_of)
    cov = np.asarray(inp.cov, dtype=float)
    n = len(inp.symbols)
    target = 1.0 / n

    def objective(w):
        sigma_p = float(np.sqrt(max(w @ cov @ w, 1e-18)))
        rc = w * (cov @ w) / (sigma_p**2)
        return float(np.sum((rc - target) ** 2))

    res = _slsqp(objective, _start(cs), cs, maxiter=800, ftol=1e-14)
    w = _finalize(res, cs, "Risk parity")
    sigma_p = float(np.sqrt(max(w @ cov @ w, 0.0)))
    rc = w * (cov @ w) / max(sigma_p**2, 1e-18)
    return {
        "weights": w,
        "volatility": sigma_p,
        "expectedReturn": float(w @ inp.mu),
        "riskShares": rc,
        "method": "risk_parity",
    }


# ------------------------------------------------------------------ strategy 5


def max_diversification(inp: OptimizationInput) -> dict:
    cs = build_constraint_set(inp.symbols, inp.constraints, inp.class_of, inp.sector_of)
    cov = np.asarray(inp.cov, dtype=float)
    vols = np.sqrt(np.clip(np.diag(cov), 0.0, None))

    def neg_dr(w):
        sigma_p = float(np.sqrt(max(w @ cov @ w, 1e-18)))
        return -float(w @ vols) / sigma_p

    res = _slsqp(neg_dr, _start(cs), cs, maxiter=600)
    w = _finalize(res, cs, "Maximum diversification")
    sigma_p = float(np.sqrt(max(w @ cov @ w, 0.0)))
    return {
        "weights": w,
        "volatility": sigma_p,
        "expectedReturn": float(w @ inp.mu),
        "diversificationRatio": (float(w @ vols) / sigma_p) if sigma_p > 0 else float("nan"),
        "method": "max_diversification",
    }


# ------------------------------------------------------------------ strategy 6


def min_cvar(inp: OptimizationInput) -> dict:
    """Minimise historical Expected Shortfall (Rockafellar-Uryasev style).

    Needs the full return matrix, so it is only run when one is supplied.
    """
    if inp.returns_matrix is None:
        raise OptimizationError("CVaR optimization requires the periodic return matrix")
    cs = build_constraint_set(inp.symbols, inp.constraints, inp.class_of, inp.sector_of)
    returns = np.asarray(inp.returns_matrix, dtype=float)
    returns = np.nan_to_num(returns, nan=0.0)
    alpha = float(inp.cvar_alpha)
    mu = np.asarray(inp.mu, dtype=float)
    target_return = inp.target_return

    def expected_shortfall(w):
        port = returns @ w
        k = max(int(np.floor((1.0 - alpha) * port.size)), 1)
        worst = np.sort(port)[:k]
        return float(-np.mean(worst))

    extra = []
    if target_return is not None:
        extra.append({"type": "ineq", "fun": lambda w: float(w @ mu) - float(target_return), "jac": lambda w: mu})

    res = _slsqp(expected_shortfall, _start(cs), cs, extra=extra, maxiter=400)
    w = _finalize(res, cs, "Minimum CVaR")
    cov = np.asarray(inp.cov, dtype=float)
    return {
        "weights": w,
        "volatility": float(np.sqrt(max(w @ cov @ w, 0.0))),
        "expectedReturn": float(w @ mu),
        "expectedShortfall": expected_shortfall(w),
        "method": "min_cvar",
    }


_DISPATCH = {
    "min_variance": min_variance,
    "max_sharpe": max_sharpe,
    "max_return_for_risk": max_return_for_risk,
    "risk_parity": risk_parity,
    "max_diversification": max_diversification,
    "min_cvar": min_cvar,
}


def optimize(strategy: str, inp: OptimizationInput) -> dict:
    if strategy not in _DISPATCH:
        raise OptimizationError(
            f"unknown optimization strategy: {strategy!r}",
            suggestions=[f"Use one of: {', '.join(STRATEGIES)}"],
        )
    return _DISPATCH[strategy](inp)
