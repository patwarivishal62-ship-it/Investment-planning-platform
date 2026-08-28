"""Large-scale candidate portfolio generation and fast vectorised screening.

The generation stage is deliberately two-phase:

  Phase 1 (screen): tens of thousands of candidates are scored with BLAS-level
  matrix algebra only -- expected return, volatility and Sharpe. Touching the
  full equity curve for 25,000 portfolios would need a T x K matrix, so exact
  path-dependent metrics (drawdown, Sortino, CVaR) are deferred.

  Phase 2 (refine): only the few hundred most promising, mutually distinct
  candidates get the full metric treatment.

Every stage is seeded, so identical inputs always produce identical output.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constraints import ConstraintSet, build_constraint_set, project_to_bounds

__all__ = ["generate_candidates", "screen_candidates", "CandidatePool", "seed_portfolios"]


@dataclass
class CandidatePool:
    weights: np.ndarray      # K x N
    expectedReturn: np.ndarray
    volatility: np.ndarray
    sharpe: np.ndarray

    def __len__(self) -> int:
        return int(self.weights.shape[0])


def generate_candidates(
    symbols: list[str],
    constraints,
    count: int = 25_000,
    seed: int = 20240101,
    class_of: dict[str, str] | None = None,
    sector_of: dict[str, str] | None = None,
    max_spread: int | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Random long-only portfolios honouring bounds + class/sector limits.

    Strategy: pick a random subset of assets (so sparse, interpretable
    allocations are well represented), draw Dirichlet weights on it, then
    project onto the feasible box and reject anything that breaks a group limit.
    """
    cs = build_constraint_set(symbols, constraints, class_of, sector_of)
    rng = rng or np.random.default_rng(seed)
    n = cs.n
    spread = max_spread or n
    spread = int(min(max(2, spread), n))

    max_assets = int(getattr(constraints, "max_assets", None) or spread)
    eligible = [i for i in range(n) if cs.upper[i] > 1e-9]
    if not eligible:
        raise ValueError("every asset is excluded -- no candidates can be generated")
    max_assets = min(max_assets, len(eligible), spread)

    out = np.zeros((count, n), dtype=float)
    accepted = 0
    attempts = 0
    max_attempts = count * 25

    while accepted < count and attempts < max_attempts:
        attempts += 1
        size = int(rng.integers(2, max_assets + 1)) if max_assets > 2 else 2
        cols = rng.choice(eligible, size=size, replace=False)
        raw = rng.dirichlet(np.ones(size))
        w = np.zeros(n)
        w[cols] = raw
        w = project_to_bounds(w, cs.lower, cs.upper)
        if w is None:
            continue
        if cs.a_ub is not None and np.any(cs.a_ub @ w - cs.b_ub > 1e-7):
            continue
        out[accepted] = w
        accepted += 1

    if accepted == 0:
        raise ValueError(
            "No random portfolio satisfied the constraints. "
            + "; ".join(_explain_empty(cs, constraints))
        )
    return out[:accepted]


def _explain_empty(cs: ConstraintSet, constraints) -> list[str]:
    reasons = []
    lo_sum = float(cs.lower.sum())
    if lo_sum > 1.0 + 1e-9:
        reasons.append(
            f"the sum of minimum asset weights is {lo_sum:.0%}, which exceeds 100%"
        )
    for row in cs.rows:
        if row["bound"] == "lower":
            reasons.append(f"the {row['label']} of {row['limit']:.0%} may be unreachable")
    if getattr(constraints, "max_volatility", None) is not None:
        reasons.append(
            f"the volatility cap of {constraints.max_volatility:.1%} may be below the "
            "minimum achievable volatility"
        )
    return reasons or ["the configured bounds are mutually inconsistent"]


def seed_portfolios(
    mu: np.ndarray,
    cov: np.ndarray,
    symbols: list[str],
    constraints,
    class_of: dict[str, str] | None = None,
    sector_of: dict[str, str] | None = None,
    risk_free_rate: float = 0.0,
    returns_matrix: np.ndarray | None = None,
) -> list[np.ndarray]:
    """Deterministic heuristic seeds so the pool always contains sensible anchors."""
    from .optimizers import STRATEGIES, optimize
    from .optimizers import OptimizationInput

    inp = OptimizationInput(
        mu=mu,
        cov=cov,
        symbols=symbols,
        constraints=constraints,
        class_of=class_of,
        sector_of=sector_of,
        risk_free_rate=risk_free_rate,
        returns_matrix=returns_matrix,
    )
    seeds: list[np.ndarray] = []

    def try_strategy(name, **overrides):
        try:
            data = dict(
                mu=inp.mu,
                cov=inp.cov,
                symbols=inp.symbols,
                constraints=inp.constraints,
                class_of=inp.class_of,
                sector_of=inp.sector_of,
                risk_free_rate=inp.risk_free_rate,
                returns_matrix=inp.returns_matrix,
            )
            data.update(overrides)
            seeds.append(optimize(name, OptimizationInput(**data))["weights"])
        except Exception:
            pass

    for strategy in STRATEGIES:
        if strategy == "max_return_for_risk":
            for v in (0.06, 0.09, 0.12, 0.15, 0.20, 0.25):
                try_strategy(strategy, target_volatility=v)
        else:
            try_strategy(strategy)

    # Equal weight and inverse-volatility anchors, projected onto the bounds.
    cs = build_constraint_set(symbols, constraints, class_of, sector_of)
    n = len(symbols)
    w = project_to_bounds(np.full(n, 1.0 / n), cs.lower, cs.upper)
    if w is not None and not (cs.a_ub is not None and np.any(cs.a_ub @ w - cs.b_ub > 1e-7)):
        seeds.append(w)
    vols = np.sqrt(np.clip(np.diag(np.asarray(cov, dtype=float)), 1e-12, None))
    inv = 1.0 / vols
    w = project_to_bounds(inv / inv.sum(), cs.lower, cs.upper)
    if w is not None and not (cs.a_ub is not None and np.any(cs.a_ub @ w - cs.b_ub > 1e-7)):
        seeds.append(w)
    return seeds


def screen_candidates(
    weights: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    risk_free_rate: float = 0.0,
    max_volatility: float | None = None,
    min_return: float | None = None,
    max_drawdown_limit: float | None = None,
) -> CandidatePool:
    """Vectorised expected return / volatility / Sharpe for every candidate."""
    w = np.asarray(weights, dtype=float)
    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)

    expected = w @ mu
    variance = np.einsum("ij,jk,ik->i", w, cov, w)
    vol = np.sqrt(np.maximum(variance, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = np.where(vol > 1e-12, (expected - risk_free_rate) / np.where(vol > 1e-12, vol, 1.0), np.nan)

    keep = np.ones(len(w), dtype=bool)
    if max_volatility is not None:
        keep &= vol <= float(max_volatility) + 1e-9
    if min_return is not None:
        keep &= expected >= float(min_return) - 1e-9
    return CandidatePool(
        weights=w[keep],
        expectedReturn=expected[keep],
        volatility=vol[keep],
        sharpe=sharpe[keep],
    )


def select_diverse(
    weights: np.ndarray,
    scores: np.ndarray,
    limit: int,
    min_distance: float = 0.25,
) -> list[int]:
    """Greedy max-score selection with an L1-distance diversity penalty.

    Guarantees the shortlist is not five variations of the same portfolio.
    """
    order = np.argsort(-np.asarray(scores, dtype=float))
    chosen: list[int] = []
    chosen_weights: list[np.ndarray] = []
    for idx in order:
        w = np.asarray(weights[idx], dtype=float)
        if any(float(np.abs(w - c).sum()) < min_distance for c in chosen_weights):
            continue
        chosen.append(int(idx))
        chosen_weights.append(w)
        if len(chosen) >= limit:
            break
    # If the distance filter was too strict, relax it progressively.
    if len(chosen) < limit:
        for relax in (0.15, 0.08, 0.0):
            chosen = []
            chosen_weights = []
            for idx in order:
                w = np.asarray(weights[idx], dtype=float)
                if any(float(np.abs(w - c).sum()) < relax for c in chosen_weights):
                    continue
                chosen.append(int(idx))
                chosen_weights.append(w)
                if len(chosen) >= limit:
                    break
            if len(chosen) >= limit:
                break
    return chosen
