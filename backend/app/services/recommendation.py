"""Recommendation engine.

Turns a universe + constraints + investor profile into 4-5 genuinely different
investment plans, each with a quantitative rationale.

Pipeline
--------
1. feasibility check (no feasible portfolio -> actionable suggestions, never a
   fabricated answer);
2. build a large candidate pool (random + deterministic strategy seeds);
3. fast vectorised screen on return / volatility / Sharpe;
4. refine a few hundred mutually distinct candidates with FULL path-dependent
   metrics (drawdown, Sortino, CVaR) using the batch engine;
5. score every refined candidate on six explicit, weighted dimensions;
6. pick one plan per investment "philosophy" band, penalising portfolios that
   are too similar to one already chosen;
7. mark the highest-scoring plan as "Best Fit" and explain every plan.

Nothing in this module is hard-coded: plan names come from the slot
definitions, but the allocations are always produced by the optimiser.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..analytics import portfolio as pf
from ..analytics.batch import batch_metrics
from ..analytics.risk_score import platform_risk_score
from ..core.config import Settings, get_settings
from ..core.logging import get_logger, log_duration
from ..data.universe import by_symbol
from ..optimization.candidates import generate_candidates, screen_candidates, seed_portfolios
from ..optimization.constraints import OptimizationConstraints
from ..optimization.diagnostics import feasibility_report, raise_infeasible
from ..optimization.optimizers import OptimizationInput, optimize
from .portfolio import PortfolioService, compute_portfolio_metrics

logger = get_logger("services.recommendation")


# ---------------------------------------------------------------- objectives
# Soft target allocations used only for the *objective alignment* sub-score.
# They are preferences expressed over asset classes, not constraints.

OBJECTIVE_TARGETS: dict[str, dict[str, float]] = {
    "capital_preservation": {"bond": 0.45, "cash": 0.20, "gold": 0.15, "equity": 0.20},
    "income": {"bond": 0.45, "reit": 0.18, "equity": 0.22, "gold": 0.10, "cash": 0.05},
    "balanced_growth": {"equity": 0.42, "bond": 0.25, "gold": 0.10, "international_equity": 0.12, "reit": 0.06, "cash": 0.05},
    "wealth_creation": {"equity": 0.52, "international_equity": 0.15, "bond": 0.15, "gold": 0.10, "reit": 0.08},
    "inflation_protection": {"equity": 0.32, "gold": 0.20, "commodity": 0.14, "international_equity": 0.10, "bond": 0.14, "reit": 0.10},
    "maximum_growth": {"equity": 0.58, "international_equity": 0.20, "reit": 0.08, "commodity": 0.07, "bond": 0.07},
}

DEFAULT_SCORING_WEIGHTS = {
    "riskAdjustedReturn": 0.35,
    "downsideRisk": 0.25,
    "diversification": 0.15,
    "drawdown": 0.10,
    "objectiveAlignment": 0.10,
    "liquidity": 0.05,
}


@dataclass
class PlanSlot:
    key: str
    name: str
    band: tuple[float, float]
    summary: str


PLAN_SLOTS: list[PlanSlot] = [
    PlanSlot("capital_preservation", "Capital Preservation", (0.00, 0.20),
             "Prioritises stability: the lowest-risk allocations that still satisfy your constraints."),
    PlanSlot("conservative_growth", "Conservative Growth", (0.18, 0.42),
             "Modest growth with a strong fixed-income and defensive core."),
    PlanSlot("balanced", "Balanced", (0.38, 0.62),
             "A middle path between growth assets and stabilising assets."),
    PlanSlot("growth", "Growth", (0.58, 0.85),
             "Growth-tilted, accepting higher volatility for a higher historical return."),
    PlanSlot("risk_optimized", "Risk-Optimized", (0.00, 1.00),
             "The best risk-adjusted outcome found anywhere in your feasible range."),
]


@dataclass
class ScoredCandidate:
    weights: np.ndarray
    metrics: dict
    score: float
    subScores: dict
    fitScore: float


class RecommendationService:
    def __init__(self, portfolio_service: PortfolioService | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.portfolio = portfolio_service or PortfolioService(settings=self.settings)

    # ------------------------------------------------------------------ main
    async def recommend(self, request) -> dict:
        snapshot = await self.portfolio._snapshot(
            getattr(request, "symbols", None), getattr(request, "start", None), getattr(request, "end", None)
        )
        symbols = snapshot.symbols
        symbols = [s for s in symbols if s not in set(getattr(request, "excluded", None) or [])]
        if len(symbols) < 2:
            raise ValueError("At least two assets are required to build a portfolio")

        rf = float(getattr(request, "riskFreeRate", None) or self.settings.risk_free_rate)
        constraints = PortfolioService._constraints_from(request)
        risk_score = float(getattr(request, "riskScore", 55.0) or 55.0)
        objective = getattr(request, "objective", None) or "balanced_growth"
        candidate_count = int(getattr(request, "candidateCount", None) or self.settings.default_candidate_portfolios)
        candidate_count = int(min(candidate_count, self.settings.max_candidate_portfolios))
        seed = int(getattr(request, "seed", None) or 20240101)
        max_positions = int(getattr(request, "maxPositions", None) or 12)
        min_holding = float(getattr(request, "minHoldingWeight", None) or 0.02)
        constraints.max_assets = max_positions

        report = feasibility_report(
            snapshot.mu, snapshot.cov, symbols, constraints,
            class_of=snapshot.class_map, sector_of=snapshot.sector_map,
            returns_matrix=snapshot.returns[symbols].to_numpy(dtype=float),
            risk_free_rate=rf,
        )
        if not report["feasible"]:
            raise raise_infeasible(report)

        with log_duration(logger, "recommend", candidates=candidate_count, assets=len(symbols)):
            pool = self._build_pool(symbols, snapshot, constraints, candidate_count, seed, rf)
            refined = self._refine(pool, symbols, snapshot, constraints, rf)
            scored = self._score(refined, snapshot, symbols, objective, risk_score, rf)
            plans = self._select_plans(scored, symbols, snapshot, objective, risk_score,
                                        report, constraints, min_holding)

        return {
            "plans": plans,
            "objective": objective,
            "riskScore": risk_score,
            "candidateCount": int(len(pool.weights)),
            "evaluatedCount": int(len(scored)),
            "feasibility": report,
            "scoringWeights": dict(getattr(request, "scoringWeights", None) or DEFAULT_SCORING_WEIGHTS),
            "assumptions": {
                "dataPeriod": f"{snapshot.start} to {snapshot.end}",
                "riskFreeRate": rf,
                "rebalance": getattr(request, "rebalanceFrequency", None) or self.settings.default_rebalance_frequency,
                "transactionCostsBps": float(getattr(request, "transactionCostBps", None) or self.settings.default_transaction_cost_bps),
                "dataQualityScore": round(snapshot.quality.score, 1),
                "optimization": "candidate search over minimum-variance / max-Sharpe / risk-parity seeds and randomised long-only portfolios",
                "candidates": int(len(pool.weights)),
                "maxPositions": max_positions,
                "minHoldingWeight": min_holding,
            },
        }

    # ------------------------------------------------------------ pool build
    def _build_pool(self, symbols, snapshot, constraints, count, seed, rf):
        rng = np.random.default_rng(seed)
        weights = generate_candidates(
            symbols, constraints, count=count, seed=seed,
            class_of=snapshot.class_map, sector_of=snapshot.sector_map, rng=rng,
        )
        mu = np.array([snapshot.mu[snapshot.symbols.index(s)] for s in symbols])
        cov = snapshot.cov[np.ix_([snapshot.symbols.index(s) for s in symbols],
                                  [snapshot.symbols.index(s) for s in symbols])]
        pool = screen_candidates(
            weights, mu, cov, risk_free_rate=rf,
            max_volatility=constraints.max_volatility or getattr(constraints, "max_volatility", None),
        )
        return pool

    # --------------------------------------------------------------- refine
    def _refine(self, pool, symbols, snapshot, constraints, rf, limit: int = 900) -> list[np.ndarray]:
        """Pick a manageable, diverse subset for full metric evaluation."""
        if len(pool) == 0:
            return []
        idx_all = np.arange(len(pool))
        chosen: list[int] = []

        def take(order, n):
            for i in order:
                if len(chosen) >= limit:
                    return
                if i not in chosen:
                    chosen.append(int(i))

        take(np.argsort(-np.nan_to_num(pool.sharpe, nan=-np.inf))[:250], 250)
        take(np.argsort(-pool.expectedReturn)[:120], 120)
        take(np.argsort(pool.volatility)[:120], 120)
        # Stratify across the volatility spectrum so every risk band is covered.
        order = idx_all[np.argsort(pool.volatility)]
        strata = np.array_split(order, min(60, len(order)))
        for block in strata:
            take(block[:6], 6)

        seen: set[tuple] = set()
        unique: list[np.ndarray] = []
        for i in chosen:
            w = pool.weights[i]
            key = tuple(np.round(w, 3))
            if key in seen:
                continue
            seen.add(key)
            unique.append(w)
        return unique[:limit]

    # ---------------------------------------------------------------- score
    def _score(self, candidates, snapshot, symbols, objective, risk_score, rf) -> list[ScoredCandidate]:
        if not candidates:
            return []
        weights_matrix = np.vstack(candidates)
        returns = snapshot.returns[symbols].to_numpy(dtype=float)
        mu = np.array([snapshot.mu[snapshot.symbols.index(s)] for s in symbols])
        metrics = batch_metrics(returns, weights_matrix, mu, snapshot.periods_per_year, rf)

        # Diversification sub-score uses two complementary measures.
        vols = np.sqrt(np.clip(np.diag(snapshot.cov), 0.0, None))
        idx = [snapshot.symbols.index(s) for s in symbols]
        vols = vols[idx]
        cov_sub = snapshot.cov[np.ix_(idx, idx)]
        weighted_avg_vol = weights_matrix @ vols
        with np.errstate(divide="ignore", invalid="ignore"):
            div_ratio = np.where(metrics["volatility"] > 1e-12, weighted_avg_vol / np.where(metrics["volatility"] > 1e-12, metrics["volatility"], 1.0), 1.0)
        effective_n = 1.0 / np.sum(weights_matrix**2, axis=1)

        liquidity = np.array([float(snapshot.liquidity_map.get(s, 0.5)) for s in symbols])
        weighted_liquidity = weights_matrix @ liquidity

        target = OBJECTIVE_TARGETS.get(objective, OBJECTIVE_TARGETS["balanced_growth"])
        classes = sorted({snapshot.class_map.get(s, "other") for s in symbols})
        target_vector = np.array([target.get(c, 0.0) for c in classes])
        if target_vector.sum() > 0:
            target_vector = target_vector / target_vector.sum()
        exposure = np.zeros((len(candidates), len(classes)))
        for j, cls in enumerate(classes):
            mask = np.array([1.0 if snapshot.class_map.get(s, "other") == cls else 0.0 for s in symbols])
            exposure[:, j] = weights_matrix @ mask
        alignment = 1.0 - 0.5 * np.abs(exposure - target_vector).sum(axis=1)

        def normalize(values, invert=False):
            values = np.asarray(values, dtype=float)
            finite = values[np.isfinite(values)]
            if finite.size == 0:
                return np.zeros_like(values)
            lo, hi = float(np.min(finite)), float(np.max(finite))
            if hi - lo < 1e-12:
                return np.full_like(values, 0.5)
            scaled = (values - lo) / (hi - lo)
            scaled = np.nan_to_num(scaled, nan=0.5)
            return 1.0 - scaled if invert else scaled

        subs = {
            "riskAdjustedReturn": normalize(metrics["sharpe"]),
            "downsideRisk": 0.5 * normalize(metrics["downsideDeviation"], invert=True)
            + 0.5 * normalize(metrics["historicalCVaR"], invert=True),
            "diversification": 0.5 * normalize(div_ratio) + 0.5 * normalize(effective_n),
            "drawdown": 0.6 * normalize(np.abs(metrics["maxDrawdown"]), invert=True)
            + 0.4 * normalize(metrics["ulcerIndex"], invert=True),
            "objectiveAlignment": np.clip(alignment, 0.0, 1.0),
            "liquidity": np.clip(weighted_liquidity, 0.0, 1.0),
        }
        weights_config = DEFAULT_SCORING_WEIGHTS
        score = sum(weights_config[k] * v for k, v in subs.items())

        # Platform risk score per candidate (needed for the risk-fit penalty).
        risk_scores = np.array([
            platform_risk_score(
                volatility=metrics["volatility"][i],
                max_drawdown=metrics["maxDrawdown"][i],
                downside_deviation=metrics["downsideDeviation"][i],
                daily_var=metrics["historicalVaR"][i],
                weights=weights_matrix[i],
                symbols=symbols,
                class_of=snapshot.class_map,
                liquidity=snapshot.liquidity_map,
            )["score"]
            for i in range(len(candidates))
        ])
        fit = score - 0.35 * (np.abs(risk_scores - risk_score) / 100.0)

        scored = []
        for i in range(len(candidates)):
            scored.append(
                ScoredCandidate(
                    weights=weights_matrix[i],
                    metrics={k: float(v[i]) for k, v in metrics.items()},
                    score=float(score[i]),
                    subScores={k: float(v[i]) for k, v in subs.items()},
                    fitScore=float(fit[i]),
                )
            )
        scored.sort(key=lambda c: c.fitScore, reverse=True)
        return scored

    # --------------------------------------------------------------- select
    def _select_plans(self, scored, symbols, snapshot, objective, risk_score, report,
                      constraints, min_holding: float = 0.02) -> list[dict]:
        if not scored:
            return []
        vols = np.array([c.metrics["volatility"] for c in scored])
        min_vol = float(np.min(vols))
        max_allowed = float(np.max(vols))

        # Risk budget: the feasible volatility range is scaled by the investor's
        # risk score, but never below 35% of it, so every profile still sees a
        # meaningful spread of plans (from "preserve capital" up to "growth").
        appetite = float(np.clip(0.35 + 0.65 * (risk_score / 100.0), 0.35, 1.0))
        ceiling = min_vol + (max_allowed - min_vol) * appetite
        if getattr(constraints, "max_volatility", None):
            ceiling = min(ceiling, float(constraints.max_volatility))
        ceiling = max(ceiling, min_vol)
        span = max(ceiling - min_vol, 1e-9)

        selected: list[ScoredCandidate] = []
        chosen_weights: list[np.ndarray] = []

        for slot in PLAN_SLOTS:
            lo, hi = slot.band
            low = min_vol + lo * span
            high = min_vol + hi * span
            if slot.key == "risk_optimized":
                low, high = -np.inf, np.inf
            candidates = [
                c for c in scored
                if low - 1e-9 <= c.metrics["volatility"] <= high + 1e-9
            ]
            if not candidates:
                # Widen the band rather than returning an empty plan.
                candidates = scored
            pick = None
            for candidate in candidates:
                if any(float(np.abs(candidate.weights - w).sum()) < 0.30 for w in chosen_weights):
                    continue
                pick = candidate
                break
            if pick is None:
                pick = candidates[0]
            selected.append(pick)
            chosen_weights.append(pick.weights)

        best_fit_index = int(np.argmax([c.fitScore for c in selected]))
        payload = []
        for i, (slot, candidate) in enumerate(zip(PLAN_SLOTS, selected)):
            # Trim sub-threshold holdings so the plan is implementable, then
            # recompute every metric from the trimmed weights so the numbers
            # shown always correspond to the allocation shown.
            final_weights = pf.consolidate_weights(
                candidate.weights,
                min_weight=min_holding,
                class_of=snapshot.class_map,
                class_bounds=getattr(constraints, "class_bounds", None) or None,
            )
            restricted = _restrict(snapshot, symbols)
            full = compute_portfolio_metrics(
                final_weights, restricted, self.settings, risk_free_rate=None
            )
            payload.append(
                {
                    "id": slot.key,
                    "name": slot.name,
                    "summary": slot.summary,
                    "bestFit": i == best_fit_index,
                    "score": round(candidate.score, 4),
                    "fitScore": round(candidate.fitScore, 4),
                    "subScores": {k: round(v, 4) for k, v in candidate.subScores.items()},
                    "metrics": full,
                    "positions": int(np.sum(final_weights > 1e-6)),
                    "explanation": explain_plan(
                        final_weights, symbols, snapshot, objective, full
                    ),
                }
            )
        return payload


def _restrict(snapshot, symbols: list[str]):
    """Return a snapshot view limited to `symbols` (used for final metrics)."""
    from dataclasses import replace

    return replace(
        snapshot,
        prices=snapshot.prices[symbols],
        returns=snapshot.returns[symbols],
        symbols=list(symbols),
        mu=np.array([snapshot.mu[snapshot.symbols.index(s)] for s in symbols]),
        cov=snapshot.cov[np.ix_([snapshot.symbols.index(s) for s in symbols],
                                 [snapshot.symbols.index(s) for s in symbols])],
        class_map={s: snapshot.class_map.get(s, "other") for s in symbols},
        sector_map={s: snapshot.sector_map.get(s, "Unknown") for s in symbols},
        liquidity_map={s: snapshot.liquidity_map.get(s, 0.5) for s in symbols},
    )


# ------------------------------------------------------------- explanations


def explain_plan(weights, symbols, snapshot, objective, metrics) -> dict:
    """Generate the 'why this portfolio?' narrative from computed numbers only.

    No metric is invented here: every sentence is derived from an array the
    engine already produced (risk contribution, return contribution,
    correlation, class exposure).
    """
    w = np.asarray(weights, dtype=float)
    idx = [snapshot.symbols.index(s) for s in symbols]
    cov_sub = snapshot.cov[np.ix_(idx, idx)]
    contribution = pf.risk_contribution(w, cov_sub, symbols)

    return_rows = metrics.get("returnContribution", [])
    risk_rows = contribution["contributions"]
    named = {s: by_symbol(s).name for s in symbols}
    class_of = snapshot.class_map

    top_return = return_rows[0] if return_rows else None
    top_risk = risk_rows[0] if risk_rows else None

    # Risk reducer: a holding whose share of risk is meaningfully below its
    # share of capital, weighted by how uncorrelated it is with the portfolio.
    portfolio_returns = snapshot.returns[symbols].to_numpy(dtype=float) @ w
    reducers = []
    for i, s in enumerate(symbols):
        if w[i] < 0.03:
            continue
        risk_share = next((r["riskShare"] for r in risk_rows if r["symbol"] == s), 0.0)
        with np.errstate(invalid="ignore"):
            asset_returns = snapshot.returns[s].to_numpy(dtype=float)
            both = np.isfinite(asset_returns) & np.isfinite(portfolio_returns)
            corr_value = (
                float(np.corrcoef(asset_returns[both], portfolio_returns[both])[0, 1])
                if both.sum() > 3 else 0.0
            )
        reducers.append(
            {
                "symbol": s,
                "name": named.get(s, s),
                "weight": float(w[i]),
                "riskShare": float(risk_share),
                "correlationToPortfolio": corr_value,
                "relief": float(w[i] - risk_share) + (0.5 * (1.0 - corr_value)),
            }
        )
    reducers.sort(key=lambda r: r["relief"], reverse=True)

    class_exposure = metrics.get("assetClassExposure", {})
    dominant_class = max(class_exposure.items(), key=lambda kv: kv[1]) if class_exposure else (None, 0)
    effective_assets = metrics.get("effectiveAssets", 0.0)
    div_ratio = metrics.get("diversificationRatio", float("nan"))

    def label(sym: str) -> str:
        return f"{named.get(sym, sym)}"

    summary = (
        f"This plan sits in the {metrics['riskScore']['band'].lower()} risk band "
        f"(Platform Risk Score {metrics['riskScore']['score']:.0f}/100) with a model-estimated "
        f"annualised return of {metrics['expectedReturn']:.1%} and annualised volatility of "
        f"{metrics['volatility']:.1%} over the selected period."
    )

    return_drivers = [
        {
            "symbol": r["symbol"],
            "name": named.get(r["symbol"], r["symbol"]),
            "weight": r["weight"],
            "shareOfReturn": r["share"],
        }
        for r in return_rows[:3]
    ]

    return {
        "summary": summary,
        "objective": objective,
        "returnDriver": {
            "text": (
                f"{label(top_return['symbol'])} contributed the largest share "
                f"({top_return['share']:.0%}) of the historical expected return."
                if top_return else "Return contributions are unavailable for this plan."
            ),
            "assets": return_drivers,
        },
        "riskReducer": {
            "text": (
                f"{reducers[0]['name']} carries {reducers[0]['weight']:.0%} of capital but only "
                f"{reducers[0]['riskShare']:.0%} of portfolio risk, and its correlation to the "
                f"portfolio over this period was {reducers[0]['correlationToPortfolio']:.2f}."
                if reducers else "No single holding provides a meaningful risk-reduction role."
            ),
            "assets": reducers[:3],
        },
        "diversification": {
            "text": (
                f"The allocation behaves like {effective_assets:.1f} equally weighted positions "
                f"(diversification ratio {div_ratio:.2f}). "
                + (
                    f"{dominant_class[0].replace('_', ' ').title()} is the largest asset-class "
                    f"exposure at {dominant_class[1]:.0%}."
                    if dominant_class[0] else ""
                )
            ),
            "effectiveAssets": effective_assets,
            "diversificationRatio": div_ratio,
            "largestAssetClass": dominant_class[0],
        },
        "mainRisk": {
            "text": (
                f"{label(top_risk['symbol'])} is the largest contributor to portfolio risk "
                f"({top_risk['riskShare']:.0%} of total volatility). The worst historical "
                f"drawdown of this allocation was {metrics['maxDrawdown']:.1%}."
                if top_risk else "Risk contributions are unavailable."
            ),
            "assets": [
                {"symbol": r["symbol"], "name": named.get(r["symbol"], r["symbol"]),
                 "weight": r["weight"], "riskShare": r["riskShare"]}
                for r in risk_rows[:3]
            ],
        },
        "caveat": (
            "These are historical, model-estimated relationships measured over the selected "
            "period. Correlations and volatilities change over time, and past behaviour does "
            "not indicate future results."
        ),
    }
