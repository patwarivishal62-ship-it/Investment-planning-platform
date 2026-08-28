"""Portfolio analytics service: the single place quantitative results are produced.

The API layer never computes anything; it validates input, calls a method here
and serialises the result. Every metric returned by this module also carries the
assumptions used to produce it (see ``assumptions_for``).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..analytics import advanced as adv
from ..analytics import correlation as corr
from ..analytics import portfolio as pf
from ..analytics import risk as riskmod
from ..analytics import statistics as stats
from ..analytics.risk_score import platform_risk_score
from ..core.config import Settings, get_settings
from ..core.logging import get_logger, log_duration
from ..data.universe import by_symbol
from ..optimization.constraints import OptimizationConstraints, build_constraint_set
from ..optimization.diagnostics import feasibility_report, raise_infeasible
from ..optimization.frontier import efficient_frontier as compute_frontier
from ..optimization.optimizers import OptimizationInput, optimize
from .market_data import MarketDataService, MarketSnapshot

logger = get_logger("services.portfolio")

CLASS_LABELS = {
    "equity": "Equity",
    "bond": "Fixed Income",
    "gold": "Gold",
    "silver": "Silver",
    "commodity": "Commodity",
    "international_equity": "International Equity",
    "reit": "REIT / InvIT",
    "cash": "Cash",
}


def assumptions_for(settings: Settings, snapshot: MarketSnapshot, **overrides) -> dict:
    """Every response carries the assumptions behind its numbers."""
    base = {
        "riskFreeRate": settings.risk_free_rate,
        "tradingDaysPerYear": settings.trading_days_per_year,
        "returnConvention": "simple",
        "annualizationMethod": "arithmetic (simple mean x periods) for expected return; geometric for CAGR",
        "varConfidence": settings.var_confidence,
        "varHorizonDays": 1,
        "dataPeriod": f"{snapshot.start} to {snapshot.end}",
        "dataStart": snapshot.start,
        "dataEnd": snapshot.end,
        "observations": int(len(snapshot.returns)),
        "dataQualityScore": round(snapshot.quality.score, 1),
        "rebalancedDailyInMetrics": True,
        "currency": "INR",
    }
    base.update({k: v for k, v in overrides.items() if v is not None})
    return base


def compute_portfolio_metrics(
    weights,
    snapshot: MarketSnapshot,
    settings: Settings,
    risk_free_rate: float | None = None,
    include_curve: bool = True,
    include_contributions: bool = True,
) -> dict:
    """Full metric bundle for one weight vector. Pure function of (weights, data)."""
    w = np.asarray(weights, dtype=float)
    symbols = snapshot.symbols
    rf = float(settings.risk_free_rate if risk_free_rate is None else risk_free_rate)
    periods = snapshot.periods_per_year

    portfolio_returns = snapshot.returns.to_numpy(dtype=float) @ w
    expected_return = float(w @ snapshot.mu)
    volatility = pf.portfolio_volatility(w, snapshot.cov)
    curve = np.cumprod(1.0 + portfolio_returns)

    mdd = riskmod.max_drawdown(curve)
    downside = riskmod.downside_deviation(portfolio_returns, mar=rf / periods, periods_per_year=periods)
    years = len(portfolio_returns) / periods
    cagr_value = float(curve[-1] ** (1 / years) - 1) if years > 0 and curve[-1] > 0 else float("nan")

    class_exposure = pf.asset_class_exposure(w, symbols, snapshot.class_map)
    liquidity = snapshot.liquidity_map
    weighted_liquidity = float(
        sum(w[i] * float(liquidity.get(s, 0.5)) for i, s in enumerate(symbols)) / (w.sum() or 1.0)
    )

    risk_score = platform_risk_score(
        volatility=volatility,
        max_drawdown=mdd,
        downside_deviation=downside,
        daily_var=riskmod.historical_var(portfolio_returns, settings.var_confidence),
        weights=w,
        symbols=symbols,
        class_of=snapshot.class_map,
        liquidity=liquidity,
    )

    result = {
        "weights": {s: float(w[i]) for i, s in enumerate(symbols)},
        "expectedReturn": expected_return,
        "cagr": cagr_value,
        "volatility": volatility,
        "sharpe": riskmod.sharpe_ratio(expected_return, volatility, rf),
        "sharpeOnCagr": riskmod.sharpe_ratio(cagr_value, volatility, rf),
        "sortino": riskmod.sortino_ratio(expected_return, downside, rf),
        "calmar": riskmod.calmar_ratio(cagr_value, mdd),
        "maxDrawdown": mdd,
        "downsideDeviation": downside,
        "ulcerIndex": riskmod.ulcer_index(curve),
        "historicalVaR": riskmod.historical_var(portfolio_returns, settings.var_confidence),
        "historicalCVaR": riskmod.historical_cvar(portfolio_returns, settings.var_confidence),
        "parametricVaR": riskmod.parametric_var(portfolio_returns, settings.var_confidence),
        "parametricCVaR": riskmod.parametric_cvar(portfolio_returns, settings.var_confidence),
        "skewness": stats.skewness(portfolio_returns),
        "kurtosis": stats.kurtosis(portfolio_returns),
        "bestPeriod": float(np.max(portfolio_returns)),
        "worstPeriod": float(np.min(portfolio_returns)),
        "positivePeriods": float(np.mean(portfolio_returns > 0)),
        "recoveryPeriods": riskmod.recovery_days(curve, periods),
        "diversificationRatio": pf.diversification_ratio(w, snapshot.annualized_vols, snapshot.cov),
        "effectiveAssets": pf.effective_n(w),
        "herfindahlIndex": pf.herfindahl_index(w),
        "assetClassExposure": class_exposure,
        "weightedLiquidity": weighted_liquidity,
        "riskScore": risk_score,
        "observations": int(len(portfolio_returns)),
    }

    if include_contributions:
        contribution = pf.risk_contribution(w, snapshot.cov, symbols)
        result["riskContribution"] = contribution["contributions"]
        # Return contribution: w_i * mu_i as a share of the total expected return.
        contributions = w * snapshot.mu
        total = float(contributions.sum())
        result["returnContribution"] = [
            {"symbol": s, "weight": float(w[i]), "contribution": float(contributions[i]),
             "share": float(contributions[i] / total) if abs(total) > 1e-12 else 0.0}
            for i, s in enumerate(symbols)
            if w[i] > 1e-6
        ]
        result["returnContribution"].sort(key=lambda r: r["contribution"], reverse=True)

    if include_curve:
        result["equityCurve"] = [float(v) for v in curve]
        result["dates"] = [str(d.date()) for d in snapshot.returns.index]
        result["drawdownSeries"] = [float(v) for v in riskmod.drawdown_series(curve)]
        result["drawdowns"] = riskmod.drawdown_table(curve, snapshot.returns.index, top=5)
    return result


class PortfolioService:
    def __init__(self, market: MarketDataService | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market = market or MarketDataService(settings=self.settings)

    # ------------------------------------------------------------------ setup
    async def _snapshot(self, symbols=None, start=None, end=None):
        return await self.market.get_snapshot(symbols, start, end)

    @staticmethod
    def _constraints_from(payload) -> OptimizationConstraints:
        return OptimizationConstraints(
            min_weight=getattr(payload, "minWeight", 0.0) or 0.0,
            max_weight=getattr(payload, "maxWeight", 1.0) or 1.0,
            asset_bounds=getattr(payload, "assetBounds", None) or {},
            class_bounds=getattr(payload, "classBounds", None) or {},
            sector_bounds=getattr(payload, "sectorBounds", None) or {},
            excluded=set(getattr(payload, "excluded", None) or []),
            max_volatility=getattr(payload, "maxVolatility", None),
            max_drawdown=getattr(payload, "maxDrawdown", None),
            min_return=getattr(payload, "minReturn", None),
            max_assets=getattr(payload, "maxAssets", None),
        )

    @staticmethod
    def _align(weights, symbols) -> dict[str, float]:
        return _align_weights(weights, symbols)

    # ---------------------------------------------------------------- analyze
    async def analyze(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        symbols = snapshot.symbols
        weights = _align_weights(request.weights, symbols)
        metrics = compute_portfolio_metrics(
            np.array([weights[s] for s in symbols], dtype=float),
            snapshot, self.settings,
            risk_free_rate=getattr(request, "riskFreeRate", None),
        )
        metrics["correlationMatrix"] = _matrix_payload(snapshot.correlation())
        metrics["covarianceMatrix"] = _matrix_payload(
            pd.DataFrame(snapshot.cov, index=symbols, columns=symbols)
        )
        metrics["assetMetrics"] = [
            _asset_row(snapshot, s, self.settings) for s in symbols if weights[s] > 1e-6
        ]
        metrics["assumptions"] = assumptions_for(self.settings, snapshot)
        metrics["symbols"] = symbols
        return metrics

    # ------------------------------------------------------------- what-if
    async def what_if(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        weights = _align_weights(request.weights, snapshot.symbols)
        before = compute_portfolio_metrics(
            np.array([weights[s] for s in snapshot.symbols], dtype=float),
            snapshot, self.settings, include_curve=False,
        )
        return {
            "metrics": before,
            "weights": before["weights"],
            "assetClassExposure": before["assetClassExposure"],
            "assumptions": assumptions_for(self.settings, snapshot),
        }

    # -------------------------------------------------------------- optimize
    async def optimize(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        constraints = self._constraints_from(request)
        rf = getattr(request, "riskFreeRate", None) or self.settings.risk_free_rate
        report = feasibility_report(
            snapshot.mu, snapshot.cov, snapshot.symbols, constraints,
            class_of=snapshot.class_map, sector_of=snapshot.sector_map,
            returns_matrix=snapshot.returns.to_numpy(dtype=float),
            risk_free_rate=rf,
        )
        if not report["feasible"]:
            raise raise_infeasible(report)

        strategies = list(getattr(request, "strategies", None) or ["min_variance", "max_sharpe", "risk_parity"])
        results = []
        for strategy in strategies:
            try:
                with log_duration(logger, "optimize", strategy=strategy, assets=len(snapshot.symbols)):
                    out = optimize(
                        strategy,
                        OptimizationInput(
                            mu=snapshot.mu, cov=snapshot.cov, symbols=snapshot.symbols,
                            constraints=constraints, class_of=snapshot.class_map,
                            sector_of=snapshot.sector_map, risk_free_rate=rf,
                            returns_matrix=snapshot.returns.to_numpy(dtype=float),
                            target_volatility=getattr(request, "targetVolatility", None),
                            target_return=getattr(request, "targetReturn", None),
                        ),
                    )
            except Exception as exc:
                logger.warning("strategy %s failed: %s", strategy, exc)
                continue
            metrics = compute_portfolio_metrics(out["weights"], snapshot, self.settings, risk_free_rate=rf)
            results.append({"strategy": strategy, "metrics": metrics})

        if not results:
            raise raise_infeasible(report)
        return {
            "results": results,
            "feasibility": report,
            "assumptions": assumptions_for(self.settings, snapshot, riskFreeRate=rf),
        }

    # ------------------------------------------------------ efficient frontier
    async def efficient_frontier(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        constraints = self._constraints_from(request)
        rf = getattr(request, "riskFreeRate", None) or self.settings.risk_free_rate
        with log_duration(logger, "efficient_frontier", assets=len(snapshot.symbols)):
            frontier = compute_frontier(
                snapshot.mu, snapshot.cov, snapshot.symbols, constraints,
                class_of=snapshot.class_map, sector_of=snapshot.sector_map,
                points=getattr(request, "points", 40) or 40, risk_free_rate=rf,
            )
        return {
            **frontier,
            "assumptions": assumptions_for(self.settings, snapshot, riskFreeRate=rf),
            "symbols": snapshot.symbols,
        }

    # ------------------------------------------------------------- correlation
    async def correlation(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        window = getattr(request, "window", None)
        frame = snapshot.returns
        if window:
            frame = frame.tail(int(window))
        matrix = corr.pearson_correlation_matrix(frame)
        payload = {
            "symbols": list(matrix.columns),
            "matrix": _matrix_payload(matrix),
            "averagePairwiseCorrelation": corr.average_pairwise_correlation(matrix),
            "window": window,
            "windowDays": int(len(frame)),
            "assumptions": assumptions_for(self.settings, snapshot),
        }
        if getattr(request, "rollingSymbol", None):
            pair = request.rollingSymbol
            if getattr(request, "rollingSymbolB", None):
                payload["rolling"] = _series_payload(
                    corr.rolling_correlation(frame, pair, request.rollingSymbolB,
                                             window=int(getattr(request, "rollingWindow", 90) or 90))
                )
        return payload

    # --------------------------------------------------- risk contribution etc
    async def risk_contribution(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        weights = _align_weights(request.weights, snapshot.symbols)
        w = np.asarray([weights[s] for s in snapshot.symbols], dtype=float)
        contribution = pf.risk_contribution(w, snapshot.cov, snapshot.symbols)
        rows = []
        for row in contribution["contributions"]:
            sym = row["symbol"]
            meta = by_symbol(sym)
            rows.append({**row, "name": meta.name, "assetClass": meta.assetClass})
        return {
            "portfolioVolatility": contribution["portfolioVolatility"],
            "contributions": rows,
            "assumptions": assumptions_for(self.settings, snapshot),
        }

    # ------------------------------------------------------------- hedging view
    async def diversification_ladder(self, request) -> dict:
        """'How diversified is your portfolio?' -- add one sleeve at a time and
        show the historical volatility / drawdown difference, in percentage
        points, over the same period."""
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        base = _align_weights(request.weights, snapshot.symbols)
        w0 = np.asarray([base[s] for s in snapshot.symbols], dtype=float)
        steps: list[dict] = [{"label": "Current allocation", "metrics": _compact(
            compute_portfolio_metrics(w0, snapshot, self.settings, include_curve=False, include_contributions=False))}]

        for label, asset_class, target in (
            ("Add Gold (10%)", "gold", 0.10),
            ("Add Fixed Income (20%)", "bond", 0.20),
            ("Add International Equity (15%)", "international_equity", 0.15),
            ("Add Commodities (5%)", "commodity", 0.05),
        ):
            members = [i for i, s in enumerate(snapshot.symbols) if snapshot.class_map.get(s) == asset_class]
            if not members:
                continue
            current = float(w0[members].sum())
            if current >= target:
                continue
            w = _tilt_to_class(w0, members, target, snapshot.symbols, snapshot.class_map)
            if w is None:
                continue
            steps.append({"label": label, "metrics": _compact(
                compute_portfolio_metrics(w, snapshot, self.settings, include_curve=False, include_contributions=False))})

        # Reference: the minimum-variance portfolio over the same universe.
        try:
            out = optimize(
                "min_variance",
                OptimizationInput(mu=snapshot.mu, cov=snapshot.cov, symbols=snapshot.symbols,
                                  constraints=OptimizationConstraints(max_weight=float(getattr(request, "maxWeight", 1.0) or 1.0)),
                                  class_of=snapshot.class_map, sector_of=snapshot.sector_map),
            )
            steps.append({"label": "Minimum-variance reference", "metrics": _compact(
                compute_portfolio_metrics(out["weights"], snapshot, self.settings,
                                          include_curve=False, include_contributions=False))})
        except Exception as exc:  # pragma: no cover
            logger.warning("min variance reference failed: %s", exc)

        base_metrics = steps[0]["metrics"]
        for step in steps[1:]:
            step["volatilityChange"] = step["metrics"]["volatility"] - base_metrics["volatility"]
            step["drawdownChange"] = step["metrics"]["maxDrawdown"] - base_metrics["maxDrawdown"]
            step["sharpeChange"] = step["metrics"]["sharpe"] - base_metrics["sharpe"]
        return {
            "steps": steps,
            "period": f"{snapshot.start} to {snapshot.end}",
            "assumptions": assumptions_for(self.settings, snapshot),
        }

    # ------------------------------------------------------------ advanced
    async def advanced_metrics(self, request) -> dict:
        snapshot = await self._snapshot(getattr(request, "symbols", None),
                                        getattr(request, "start", None),
                                        getattr(request, "end", None))
        weights = _align_weights(request.weights, snapshot.symbols)
        w = np.asarray([weights[s] for s in snapshot.symbols], dtype=float)
        port = pd.Series(snapshot.returns.to_numpy(dtype=float) @ w, index=snapshot.returns.index)
        benchmark_symbol = getattr(request, "benchmark", None) or "NIFTY50"
        bench = snapshot.returns[benchmark_symbol] if benchmark_symbol in snapshot.returns.columns else None
        payload = {
            "rollingVolatility": _series_payload(adv.rolling_volatility(port, window=63)),
            "rollingSharpe": _series_payload(adv.rolling_sharpe(port, window=252, risk_free_rate=self.settings.risk_free_rate)),
            "rollingReturn": _series_payload(adv.rolling_return(port, window=252)),
            "distribution": _distribution_payload(port),
            "pca": adv.principal_components(snapshot.returns),
        }
        if bench is not None:
            payload["benchmark"] = benchmark_symbol
            payload["betaAlpha"] = adv.beta_alpha(port, bench, self.settings.risk_free_rate)
            payload["trackingError"] = adv.tracking_error(port, bench)
            payload["informationRatio"] = adv.information_ratio(port, bench)
            payload["captureRatios"] = adv.capture_ratios(port, bench)
        return payload


# --------------------------------------------------------------------- helpers


def _align_weights(weights: dict[str, float] | list[float], symbols: list[str]) -> dict[str, float]:
    """Map user weights onto the snapshot's symbol order, normalising to 1."""
    if isinstance(weights, dict):
        raw = np.array([float(weights.get(s, 0.0)) for s in symbols], dtype=float)
    else:
        raw = np.asarray(weights, dtype=float)
        if raw.shape[0] != len(symbols):
            raise ValueError(f"expected {len(symbols)} weights, received {raw.shape[0]}")
    if raw.size == 0 or raw.sum() <= 0:
        raise ValueError("At least one weight must be positive")
    if np.any(raw < -1e-9):
        raise ValueError("Negative weights are not supported")
    normalised = pf.normalize_weights(raw)
    return {s: float(normalised[i]) for i, s in enumerate(symbols)}


def _matrix_payload(frame: pd.DataFrame) -> list[list[float | None]]:
    values = frame.to_numpy(dtype=float)
    return [[None if not np.isfinite(v) else float(v) for v in row] for row in values]


def _series_payload(series: pd.Series) -> list[dict]:
    out = []
    for ts, value in series.dropna().items():
        out.append({"date": str(pd.Timestamp(ts).date()), "value": float(value)})
    return out


def _distribution_payload(series: pd.Series, bins: int = 40) -> dict:
    values = series.dropna().to_numpy(dtype=float)
    if values.size == 0:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(values, bins=bins)
    centers = ((edges[:-1] + edges[1:]) / 2).tolist()
    return {
        "bins": [float(c) for c in centers],
        "counts": [int(c) for c in counts],
        "statistics": stats.describe(values),
    }


def _asset_row(snapshot: MarketSnapshot, symbol: str, settings: Settings) -> dict:
    series = snapshot.returns[symbol].to_numpy(dtype=float)
    m = riskmod.risk_metrics_summary(series, snapshot.periods_per_year, settings.risk_free_rate)
    meta = by_symbol(symbol)
    return {
        "symbol": symbol,
        "name": meta.name,
        "assetClass": meta.assetClass,
        "annualizedReturn": m.get("annualizedReturn"),
        "volatility": m.get("volatility"),
        "sharpe": m.get("sharpe"),
        "sortino": m.get("sortino"),
        "maxDrawdown": m.get("maxDrawdown"),
    }


def _compact(metrics: dict) -> dict:
    keep = ("expectedReturn", "volatility", "sharpe", "sortino", "maxDrawdown",
            "historicalCVaR", "diversificationRatio", "effectiveAssets", "cagr")
    out = {k: metrics[k] for k in keep if k in metrics}
    out["riskScore"] = metrics["riskScore"]["score"]
    out["assetClassExposure"] = metrics.get("assetClassExposure", {})
    out["weights"] = metrics.get("weights", {})
    return out


def _tilt_to_class(w0: np.ndarray, members: list[int], target: float, symbols, class_map) -> np.ndarray | None:
    """Raise a class to `target`, funding it pro-rata from the other holdings."""
    w = w0.copy()
    others = [i for i in range(len(w)) if i not in members]
    if not others:
        return None
    current = float(w[members].sum())
    needed = target - current
    if needed <= 0:
        return None
    available = float(w[others].sum())
    if available <= 1e-9:
        return None
    scale = max(0.0, 1.0 - needed / available)
    w[others] = w[others] * scale
    shortfall = target - float(w[members].sum())
    if shortfall > 0 and current > 0:
        w[members] = w[members] * (target / current)
    elif shortfall > 0:
        w[members] = w[members] + shortfall / len(members)
    total = float(w.sum())
    return w / total if total > 0 else None
