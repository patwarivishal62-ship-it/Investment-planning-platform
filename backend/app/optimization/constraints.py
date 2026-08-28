"""Declarative constraint model shared by every optimizer.

Constraints are stated once, translated to bounds + linear inequality
matrices, and reused by SciPy, by the random candidate generator and by the
infeasibility diagnostics so those three can never disagree.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = ["OptimizationConstraints", "ConstraintSet", "build_constraint_set", "OptimizationError"]


class OptimizationError(Exception):
    """Raised when no portfolio satisfies the constraints, with a human reason."""

    def __init__(self, message: str, suggestions: list[str] | None = None, detail: dict | None = None):
        super().__init__(message)
        self.suggestions = suggestions or []
        self.detail = detail or {}


@dataclass
class OptimizationConstraints:
    min_weight: float = 0.0
    max_weight: float = 1.0
    asset_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    class_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    sector_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    excluded: set[str] = field(default_factory=set)
    max_volatility: float | None = None
    max_drawdown: float | None = None
    min_return: float | None = None
    max_assets: int | None = None


@dataclass
class ConstraintSet:
    """Numeric form of the constraints for a concrete symbol ordering."""

    symbols: list[str]
    n: int
    lower: np.ndarray
    upper: np.ndarray
    a_ub: np.ndarray | None
    b_ub: np.ndarray | None
    rows: list[dict] = field(default_factory=list)

    def as_bounds(self) -> list[tuple[float, float]]:
        return [(float(self.lower[i]), float(self.upper[i])) for i in range(self.n)]

    def feasible_point(self) -> np.ndarray | None:
        """A cheap starting point: equal weight over the unconstrained assets."""
        w = np.full(self.n, 1.0 / self.n)
        return project_to_bounds(w, self.lower, self.upper)

    def violations(self, weights, tol: float = 1e-6) -> list[str]:
        w = np.asarray(weights, dtype=float)
        problems = []
        if abs(float(w.sum()) - 1.0) > 1e-4:
            problems.append(f"weights sum to {w.sum():.4f}, not 1.0")
        if np.any(w < self.lower - 1e-6):
            problems.append("an asset is below its minimum weight")
        if np.any(w > self.upper + 1e-6):
            problems.append("an asset is above its maximum weight")
        if self.a_ub is not None and self.b_ub is not None:
            slack = self.a_ub @ w - self.b_ub
            for i, s in enumerate(slack):
                if s > 1e-6:
                    label = self.rows[i]["label"] if i < len(self.rows) else f"constraint {i}"
                    problems.append(f"{label} exceeded by {s:.2%}")
        return problems


def project_to_bounds(w: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray | None:
    """Clamp to [lower, upper] and redistribute the surplus/deficit iteratively."""
    w = np.clip(np.asarray(w, dtype=float), lower, upper)
    for _ in range(64):
        diff = 1.0 - float(w.sum())
        if abs(diff) < 1e-10:
            return w
        if diff > 0:
            room = upper - w
        else:
            room = w - lower
        capacity = float(room.sum())
        if capacity <= 1e-12:
            return None
        w = w + room * (diff / capacity)
        w = np.clip(w, lower, upper)
    return None


def build_constraint_set(
    symbols: list[str],
    constraints: OptimizationConstraints,
    class_of: dict[str, str] | None = None,
    sector_of: dict[str, str] | None = None,
) -> ConstraintSet:
    """Translate declarative constraints into bounds + A_ub w <= b_ub rows."""
    class_of = class_of or {}
    sector_of = sector_of or {}
    n = len(symbols)
    excluded = {s for s in constraints.excluded if s in symbols}
    lower = np.full(n, max(0.0, float(constraints.min_weight)))
    upper = np.full(n, min(1.0, float(constraints.max_weight)))

    for i, sym in enumerate(symbols):
        if sym in excluded:
            lower[i] = 0.0
            upper[i] = 0.0
        elif sym in constraints.asset_bounds:
            lo, hi = constraints.asset_bounds[sym]
            lower[i] = max(lower[i], float(lo))
            upper[i] = min(upper[i], float(hi))
    lower = np.minimum(lower, upper)

    rows: list[dict] = []
    a_rows: list[np.ndarray] = []
    b_vals: list[float] = []

    def add_group_bounds(bounds: dict[str, tuple[float, float]], mapping: dict[str, str], kind: str):
        for key, (lo, hi) in bounds.items():
            members = [i for i, s in enumerate(symbols) if mapping.get(s) == key]
            if not members:
                continue
            mask = np.zeros(n)
            mask[members] = 1.0
            if hi is not None:
                a_rows.append(mask.copy())
                b_vals.append(float(hi))
                rows.append({"kind": kind, "label": f"max {kind} '{key}'", "limit": float(hi), "bound": "upper", "group": key})
            if lo is not None and lo > 0:
                a_rows.append(-mask)
                b_vals.append(-float(lo))
                rows.append({"kind": kind, "label": f"min {kind} '{key}'", "limit": float(lo), "bound": "lower", "group": key})

    add_group_bounds(constraints.class_bounds, class_of, "asset class")
    add_group_bounds(constraints.sector_bounds, sector_of, "sector")

    a_ub = np.vstack(a_rows) if a_rows else None
    b_ub = np.array(b_vals) if b_vals else None
    return ConstraintSet(
        symbols=symbols,
        n=n,
        lower=lower,
        upper=upper,
        a_ub=a_ub,
        b_ub=b_ub,
        rows=rows,
    )
