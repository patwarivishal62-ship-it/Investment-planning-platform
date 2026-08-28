"""Constraint feasibility diagnostics.

When a request has no feasible portfolio we explain *which* constraint is the
binding one and what value would make it feasible -- never a generic 500 and
never a silently fabricated portfolio.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

from .constraints import OptimizationConstraints, OptimizationError, build_constraint_set

__all__ = ["feasibility_report", "suggest_relaxations"]


def _bounds_feasible(cs) -> tuple[bool, list[str]]:
    """LP feasibility of the linear (non-risk) constraints."""
    n = cs.n
    result = linprog(
        c=np.zeros(n),
        A_ub=cs.a_ub,
        b_ub=cs.b_ub,
        A_eq=np.ones((1, n)),
        b_eq=np.array([1.0]),
        bounds=cs.as_bounds(),
        method="highs",
    )
    if result.success:
        return True, []
    problems = []
    lo_sum = float(cs.lower.sum())
    if lo_sum > 1.0 + 1e-9:
        problems.append(
            f"The minimum weights across all selected assets add up to {lo_sum:.0%}, "
            "which is more than 100%."
        )
    lower_groups = [r for r in cs.rows if r["bound"] == "lower"]
    total_lower = sum(r["limit"] for r in lower_groups)
    if total_lower > 1.0 + 1e-9:
        problems.append(
            "The minimum allocations required for "
            + ", ".join(f"{r['group']} {r['limit']:.0%}" for r in lower_groups)
            + f" add up to {total_lower:.0%}, more than 100%."
        )
    for r in lower_groups:
        problems.append(
            f"The minimum {r['kind']} allocation of {r['limit']:.0%} for '{r['group']}' "
            "may be unreachable given the per-asset caps."
        )
    if not problems:
        problems.append("The allocation bounds conflict with each other.")
    return False, problems


def feasibility_report(
    mu: np.ndarray,
    cov: np.ndarray,
    symbols: list[str],
    constraints: OptimizationConstraints,
    class_of: dict[str, str] | None = None,
    sector_of: dict[str, str] | None = None,
    returns_matrix: np.ndarray | None = None,
    risk_free_rate: float = 0.0,
) -> dict:
    """Quantify the feasible region and list the binding constraints."""
    from .optimizers import OptimizationInput, max_return_for_risk, min_variance

    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)
    cs = build_constraint_set(symbols, constraints, class_of, sector_of)

    linear_ok, linear_problems = _bounds_feasible(cs)
    report: dict = {
        "linearFeasible": linear_ok,
        "problems": list(linear_problems),
        "suggestions": [],
        "minVolatility": None,
        "maxVolatility": None,
        "maxReturnAtVolatilityCap": None,
        "minDrawdownAtMinVariance": None,
        "feasible": linear_ok,
    }
    if not linear_ok:
        report["suggestions"] = linear_problems[:]
        return report

    inp = OptimizationInput(
        mu=mu, cov=cov, symbols=symbols, constraints=constraints,
        class_of=class_of, sector_of=sector_of, risk_free_rate=risk_free_rate,
        returns_matrix=returns_matrix,
    )
    min_var = min_variance(inp)
    report["minVolatility"] = float(min_var["volatility"])
    allowed = cs.upper > 1e-9
    report["maxVolatility"] = float(np.max(np.sqrt(np.clip(np.diag(cov), 0.0, None))[allowed]))

    cap = getattr(constraints, "max_volatility", None)
    if cap is not None and cap < report["minVolatility"]:
        report["feasible"] = False
        report["problems"].append(
            f"Maximum volatility of {cap:.1%} is below the lowest achievable "
            f"volatility of {report['minVolatility']:.1%}."
        )
        report["suggestions"].append(
            f"Increase the maximum volatility from {cap:.1%} to at least "
            f"{report['minVolatility'] + 0.005:.1%}."
        )
        report["suggestions"].append(
            "Alternatively add lower-risk assets (bonds, cash) or allow a larger "
            "allocation to them."
        )

    target_vol = cap if cap is not None else report["maxVolatility"]
    try:
        best = max_return_for_risk(
            OptimizationInput(**{**inp.__dict__, "target_volatility": float(target_vol)})
        )
        report["maxReturnAtVolatilityCap"] = float(best["expectedReturn"])
    except Exception:
        report["maxReturnAtVolatilityCap"] = None

    if constraints.min_return is not None and report["maxReturnAtVolatilityCap"] is not None:
        if constraints.min_return > report["maxReturnAtVolatilityCap"]:
            report["feasible"] = False
            report["problems"].append(
                f"Minimum expected return of {constraints.min_return:.1%} exceeds the "
                f"{report['maxReturnAtVolatilityCap']:.1%} achievable within the risk cap."
            )
            report["suggestions"].append(
                f"Lower the minimum expected return to {report['maxReturnAtVolatilityCap']:.1%} "
                "or raise the volatility limit."
            )

    # Drawdown feasibility is only checkable against history, so we measure the
    # drawdown of the *lowest risk* portfolio and treat that as the floor.
    if returns_matrix is not None and np.asarray(returns_matrix).size:
        r = np.nan_to_num(np.asarray(returns_matrix, dtype=float), nan=0.0)
        port = r @ min_var["weights"]
        curve = np.cumprod(1.0 + port)
        peaks = np.maximum.accumulate(curve)
        mdd = float(np.min(np.where(peaks > 0, curve / peaks - 1.0, 0.0)))
        report["minDrawdownAtMinVariance"] = mdd
        if constraints.max_drawdown is not None and constraints.max_drawdown < abs(mdd):
            report["problems"].append(
                f"Maximum drawdown limit of {abs(constraints.max_drawdown):.1%} is tighter "
                f"than the {abs(mdd):.1%} worst historical drawdown of the lowest-risk "
                "portfolio in this universe."
            )
            report["suggestions"].append(
                f"Relax the drawdown limit to about {abs(mdd) + 0.02:.0%}, or accept that "
                "no portfolio in this universe has historically stayed within it."
            )
    return report


def suggest_relaxations(report: dict) -> list[str]:
    return report.get("suggestions", [])


def raise_infeasible(report: dict) -> OptimizationError:
    suggestion = report["suggestions"][0] if report["suggestions"] else "Relax a constraint and retry."
    return OptimizationError(
        "No portfolio satisfies your current constraints. " + suggestion,
        suggestions=report["suggestions"],
        detail=report,
    )
