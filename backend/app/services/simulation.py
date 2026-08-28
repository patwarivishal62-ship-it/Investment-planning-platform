"""Backtesting, rebalancing studies, Monte Carlo, stress testing, walk-forward.

Look-ahead control: the walk-forward routine optimises only on the training
window, then applies the resulting weights to a strictly later test window.
The backtest simulator itself only ever uses returns already realised at each
step (see app/analytics/backtest.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..analytics import advanced as adv
from ..analytics import portfolio as pf
from ..analytics import risk as riskmod
from ..analytics.backtest import simulate_portfolio
from ..analytics.monte_carlo import monte_carlo as run_monte_carlo
from ..analytics.stress import (
    SCENARIOS,
    apply_scenario,
    historical_stress_windows,
    replay_window,
)
from ..core.config import Settings, get_settings
from ..core.logging import get_logger, log_duration
from ..optimization.constraints import OptimizationConstraints
from ..optimization.optimizers import OptimizationInput, optimize
from .market_data import MarketDataService
from .portfolio import PortfolioService

logger = get_logger("services.simulation")

BENCHMARKS = ["NIFTY50", "GOLD", "GSEC10Y"]


def summarize_curve(
    dates: pd.DatetimeIndex,
    equity: np.ndarray,
    returns: np.ndarray,
    periods_per_year: int,
    risk_free_rate: float,
    contributions: float = 0.0,
    contribution_dates: list[str] | None = None,
    initial_value: float | None = None,
) -> dict:
    """Headline backtest statistics.

    Two different things are reported deliberately, because conflating them is
    the classic way a backtest lies:

    * ``cagr`` / ``totalReturn`` are TIME-WEIGHTED: they compound the periodic
      returns only, so cash inflows never inflate the performance number.
    * ``endValue`` / ``moneyWeightedReturn`` describe the ACCOUNT, i.e. what the
      investor's balance actually did including every contribution.

    Drawdown is measured on the time-weighted curve; on the contribution-inflated
    account curve it would be understated, since fresh cash masks the fall.
    """
    years = len(returns) / periods_per_year if periods_per_year else float("nan")
    # Time-weighted performance curve (no cash flows).
    twr_curve = np.cumprod(1.0 + returns)
    growth = float(twr_curve[-1]) if twr_curve.size else float("nan")
    cagr = float(growth ** (1 / years) - 1) if years > 0 and growth > 0 else float("nan")
    vol = riskmod.annualized_volatility(returns, periods_per_year)
    mdd = riskmod.max_drawdown(twr_curve)
    downside = riskmod.downside_deviation(returns, mar=risk_free_rate / periods_per_year,
                                          periods_per_year=periods_per_year)

    start_value = float(initial_value if initial_value is not None else (equity[0] if len(equity) else 0.0))
    end_value = float(equity[-1]) if len(equity) else None
    per_contribution = (contributions / max(len(contribution_dates or []), 1)) if contribution_dates else 0.0
    mwr = money_weighted_return(
        initial_value=start_value,
        periodic_contribution=per_contribution,
        n_contributions=len(contribution_dates or []),
        years=years,
        final_value=end_value or 0.0,
    )
    return {
        "startValue": start_value,
        "endValue": end_value,
        "invested": start_value + float(contributions),
        "totalReturn": growth - 1.0 if np.isfinite(growth) else float("nan"),
        "cagr": cagr,
        "moneyWeightedReturn": mwr,
        "annualizedReturn": riskmod_annual(returns, periods_per_year),
        "volatility": vol,
        "sharpe": riskmod.sharpe_ratio(cagr, vol, risk_free_rate),
        "sortino": riskmod.sortino_ratio(cagr, downside, risk_free_rate),
        "calmar": riskmod.calmar_ratio(cagr, mdd),
        "maxDrawdown": mdd,
        "recoveryPeriods": riskmod.recovery_days(twr_curve, periods_per_year),
        "bestPeriod": float(np.max(returns)) if returns.size else None,
        "worstPeriod": float(np.min(returns)) if returns.size else None,
        "winningPeriods": int(np.sum(returns > 0)),
        "losingPeriods": int(np.sum(returns < 0)),
        "winRate": float(np.mean(returns > 0)) if returns.size else None,
        "contributions": float(contributions),
        "years": years,
    }


def money_weighted_return(
    initial_value: float,
    periodic_contribution: float,
    n_contributions: int,
    years: float,
    final_value: float,
) -> float:
    """Annualised IRR of the contribution schedule (bisection on the NPV)."""
    if years <= 0 or initial_value <= 0 or final_value <= 0:
        return float("nan")

    def npv(rate: float) -> float:
        discount = (1.0 + rate) ** years
        value = -initial_value + final_value / discount
        for i in range(int(n_contributions)):
            t = years * (i + 1) / max(int(n_contributions), 1)
            value -= periodic_contribution / ((1.0 + rate) ** t)
        return value

    lo, hi = -0.9, 5.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return float((lo + hi) / 2.0)


def riskmod_annual(returns: np.ndarray, periods_per_year: int) -> float:
    from ..analytics import returns as ret

    return ret.annualized_return(returns, periods_per_year, method="arithmetic")


class SimulationService:
    def __init__(self, market: MarketDataService | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market = market or MarketDataService(settings=self.settings)
        self.portfolio = PortfolioService(market=self.market, settings=self.settings)

    # ------------------------------------------------------------- backtest
    async def backtest(self, request) -> dict:
        snapshot = await self.portfolio._snapshot(getattr(request, "symbols", None),
                                                  getattr(request, "start", None),
                                                  getattr(request, "end", None))
        symbols = snapshot.symbols
        weights = self.portfolio._align(request.weights, symbols)
        w = np.array([weights[s] for s in symbols], dtype=float)
        rf = float(getattr(request, "riskFreeRate", None) or self.settings.risk_free_rate)
        cost = float(getattr(request, "transactionCostBps", None) if getattr(request, "transactionCostBps", None) is not None else self.settings.default_transaction_cost_bps)
        frequency = getattr(request, "rebalanceFrequency", None) or self.settings.default_rebalance_frequency

        with log_duration(logger, "backtest", periods=len(snapshot.returns), rebalance=frequency):
            result = simulate_portfolio(
                snapshot.returns[symbols],
                w,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                periodic_contribution=float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                contribution_frequency=getattr(request, "contributionFrequency", "monthly") or "monthly",
                rebalance_frequency=frequency,
                rebalance_threshold=float(getattr(request, "rebalanceThreshold", 0.10) or 0.10),
                transaction_cost_bps=cost,
            )

        summary = summarize_curve(
            pd.DatetimeIndex(snapshot.returns.index), result.equity, result.returns,
            snapshot.periods_per_year, rf, result.total_contributions,
            contribution_dates=result.contribution_dates,
            initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
        )
        summary["totalCosts"] = float(result.total_costs)
        summary["totalTurnover"] = float(result.total_turnover)
        summary["rebalanceEvents"] = len(result.rebalance_dates)

        # Calendar-year performance.
        yearly = pd.Series(result.returns, index=pd.DatetimeIndex(snapshot.returns.index))
        compounded = (1 + yearly).resample("YE").prod() - 1
        calendar = [{"year": str(ts.year), "return": float(v)} for ts, v in compounded.items()]
        best_year = max(calendar, key=lambda c: c["return"]) if calendar else None
        worst_year = min(calendar, key=lambda c: c["return"]) if calendar else None

        comparisons = []
        for symbol in BENCHMARKS:
            if symbol not in snapshot.returns.columns:
                continue
            bench = simulate_portfolio(
                snapshot.returns[[symbol]],
                np.array([1.0]),
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                periodic_contribution=float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                contribution_frequency=getattr(request, "contributionFrequency", "monthly") or "monthly",
                rebalance_frequency="none",
                transaction_cost_bps=0.0,
            )
            comparisons.append({
                "symbol": symbol,
                "name": self.market.metadata(symbol)["name"],
                **summarize_curve(pd.DatetimeIndex(snapshot.returns.index), bench.equity, bench.returns,
                                  snapshot.periods_per_year, rf, bench.total_contributions,
                                  contribution_dates=bench.contribution_dates,
                                  initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0)),
                "equityCurve": [float(v) for v in bench.equity],
            })

        return {
            "portfolio": {
                **summary,
                "bestYear": best_year,
                "worstYear": worst_year,
                "calendarYears": calendar,
                "equityCurve": [float(v) for v in result.equity],
                "performanceCurve": [float(v) for v in np.cumprod(1.0 + result.returns)],
                "drawdownSeries": [float(v) for v in riskmod.drawdown_series(np.cumprod(1.0 + result.returns))],
                "dates": result.dates,
                "weights": {s: float(w[i]) for i, s in enumerate(symbols)},
                "finalWeights": {s: float(result.weights_history[-1][i]) for i, s in enumerate(symbols)},
            },
            "benchmarks": comparisons,
            "assumptions": {
                "rebalanceFrequency": frequency,
                "transactionCostBps": cost,
                "riskFreeRate": rf,
                "dataPeriod": f"{snapshot.start} to {snapshot.end}",
                "initialValue": float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                "monthlyContribution": float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                "costsAreAssumptions": True,
                "taxesNotModelled": True,
            },
        }

    # --------------------------------------------------- rebalancing compare
    async def rebalance_compare(self, request) -> dict:
        snapshot = await self.portfolio._snapshot(getattr(request, "symbols", None),
                                                  getattr(request, "start", None),
                                                  getattr(request, "end", None))
        symbols = snapshot.symbols
        weights = self.portfolio._align(request.weights, symbols)
        w = np.array([weights[s] for s in symbols], dtype=float)
        rf = float(getattr(request, "riskFreeRate", None) or self.settings.risk_free_rate)
        cost = float(getattr(request, "transactionCostBps", None) if getattr(request, "transactionCostBps", None) is not None else self.settings.default_transaction_cost_bps)
        results = []
        for frequency in ("none", "monthly", "quarterly", "semiannual", "annual", "threshold"):
            result = simulate_portfolio(
                snapshot.returns[symbols], w,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                periodic_contribution=float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                rebalance_frequency=frequency,
                rebalance_threshold=float(getattr(request, "rebalanceThreshold", 0.10) or 0.10),
                transaction_cost_bps=cost,
            )
            summary = summarize_curve(
                pd.DatetimeIndex(snapshot.returns.index), result.equity,
                result.returns, snapshot.periods_per_year, rf, result.total_contributions,
                contribution_dates=result.contribution_dates,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
            )
            summary.update({
                "frequency": frequency,
                "label": {"none": "Buy & Hold", "monthly": "Monthly", "quarterly": "Quarterly",
                          "semiannual": "Semi-annual", "annual": "Annual",
                          "threshold": "Threshold-based"}[frequency],
                "totalCosts": float(result.total_costs),
                "totalTurnover": float(result.total_turnover),
                "rebalanceEvents": len(result.rebalance_dates),
                "endValue": float(result.final_value),
            })
            results.append(summary)
        return {
            "results": results,
            "assumptions": {
                "transactionCostBps": cost,
                "riskFreeRate": rf,
                "dataPeriod": f"{snapshot.start} to {snapshot.end}",
            },
        }

    # ---------------------------------------------------------------- monte carlo
    async def monte_carlo(self, request) -> dict:
        snapshot = await self.portfolio._snapshot(getattr(request, "symbols", None),
                                                  getattr(request, "start", None),
                                                  getattr(request, "end", None))
        symbols = snapshot.symbols
        weights = self.portfolio._align(request.weights, symbols)
        w = np.array([weights[s] for s in symbols], dtype=float)
        paths = int(min(getattr(request, "paths", 10000) or 10000, self.settings.max_monte_carlo_paths))
        with log_duration(logger, "monte_carlo", paths=paths):
            result = run_monte_carlo(
                weights=w,
                mu_annual=snapshot.mu,
                cov_annual=snapshot.cov,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                periodic_contribution=float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                years=float(getattr(request, "years", 10.0) or 10.0),
                paths=paths,
                seed=getattr(request, "seed", 42),
                method=getattr(request, "method", "normal") or "normal",
                steps_per_year=int(getattr(request, "stepsPerYear", 12) or 12),
                annual_contribution_increase=float(getattr(request, "annualContributionIncrease", 0.0) or 0.0),
                historical_returns=snapshot.returns[symbols].to_numpy(dtype=float) @ w,
            )
        result["assumptions"] = {
            **result["assumptions"],
            "dataPeriod": f"{snapshot.start} to {snapshot.end}",
            "riskFreeRate": self.settings.risk_free_rate,
            "illustrativeOnly": True,
        }
        result["weights"] = {s: float(w[i]) for i, s in enumerate(symbols)}
        return result

    # ------------------------------------------------------------ stress test
    async def stress_test(self, request) -> dict:
        snapshot = await self.portfolio._snapshot(getattr(request, "symbols", None),
                                                  getattr(request, "start", None),
                                                  getattr(request, "end", None))
        symbols = snapshot.symbols
        weights = self.portfolio._align(request.weights, symbols)
        w = np.array([weights[s] for s in symbols], dtype=float)
        value = float(getattr(request, "portfolioValue", None) or 1_000_000.0)

        scenarios_payload = []
        keys = list(getattr(request, "scenarios", None) or SCENARIOS.keys())
        for key in keys:
            if key == "custom":
                shocks = getattr(request, "customShocks", None) or []
                scenario = {"name": "Custom Scenario", "description": "User-defined shocks.", "shocks": shocks}
            else:
                scenario = SCENARIOS.get(key)
                if scenario is None:
                    continue
            result = apply_scenario(w, symbols, snapshot.class_map, scenario["shocks"], value=value)
            scenarios_payload.append({
                "key": key,
                "name": scenario["name"],
                "description": scenario["description"],
                "shocks": scenario["shocks"],
                **result,
            })

        portfolio_returns = snapshot.returns[symbols].to_numpy(dtype=float) @ w
        windows = historical_stress_windows(
            pd.Series(portfolio_returns, index=snapshot.returns.index),
            dates=snapshot.returns.index,
            window_days=int(getattr(request, "windowDays", 60) or 60),
            top=int(getattr(request, "historicalWindows", 5) or 5),
        )
        return {
            "scenarios": scenarios_payload,
            "historicalWindows": windows,
            "portfolioValue": value,
            "weights": {s: float(w[i]) for i, s in enumerate(symbols)},
            "assumptions": {
                "dataPeriod": f"{snapshot.start} to {snapshot.end}",
                "scenariosAreHypothetical": True,
                "historicalWindowsAreObserved": True,
            },
        }

    # ---------------------------------------------------------- walk forward
    async def walk_forward(self, request) -> dict:
        """Optimise on a training window, then evaluate strictly out-of-sample."""
        snapshot = await self.portfolio._snapshot(getattr(request, "symbols", None),
                                                  getattr(request, "start", None),
                                                  getattr(request, "end", None))
        train_end = str(getattr(request, "trainEnd"))
        returns = snapshot.returns
        train = returns.loc[:train_end]
        test = returns.loc[pd.Timestamp(train_end) + pd.Timedelta(days=1):]
        if len(train) < 60 or len(test) < 20:
            raise ValueError(
                f"Not enough data for a walk-forward split at {train_end}: "
                f"{len(train)} training periods and {len(test)} test periods."
            )

        symbols = list(returns.columns)
        rf = float(getattr(request, "riskFreeRate", None) or self.settings.risk_free_rate)
        constraints = PortfolioService._constraints_from(request)
        strategy = getattr(request, "strategy", "max_sharpe") or "max_sharpe"

        mu_train = (train.mean() * snapshot.periods_per_year).to_numpy(dtype=float)
        cov_train = (train.cov() * snapshot.periods_per_year).to_numpy(dtype=float)
        from ..analytics.correlation import nearest_psd

        cov_train = nearest_psd(cov_train)
        with log_duration(logger, "walk_forward_optimize", strategy=strategy, train_days=len(train)):
            outcome = optimize(
                strategy,
                OptimizationInput(mu=mu_train, cov=cov_train, symbols=symbols,
                                  constraints=constraints, class_of=snapshot.class_map,
                                  sector_of=snapshot.sector_map, risk_free_rate=rf,
                                  returns_matrix=train.to_numpy(dtype=float),
                                  target_volatility=getattr(request, "targetVolatility", None)),
            )
        weights = outcome["weights"]
        cost = float(getattr(request, "transactionCostBps", None) if getattr(request, "transactionCostBps", None) is not None else self.settings.default_transaction_cost_bps)

        def evaluate(frame, label):
            result = simulate_portfolio(
                frame, weights,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                periodic_contribution=float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                rebalance_frequency=getattr(request, "rebalanceFrequency", "quarterly") or "quarterly",
                transaction_cost_bps=cost,
            )
            summary = summarize_curve(
                pd.DatetimeIndex(frame.index), result.equity, result.returns,
                snapshot.periods_per_year, rf, result.total_contributions,
                contribution_dates=result.contribution_dates,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
            )
            summary.update({
                "label": label,
                "start": str(frame.index[0].date()),
                "end": str(frame.index[-1].date()),
                "equityCurve": [float(v) for v in result.equity],
                # Time-weighted: compounds performance only, so contributions
                # cannot inflate the curve. Kept separate from equityCurve,
                # which is the account balance including cash inflows.
                "performanceCurve": [float(v) for v in np.cumprod(1.0 + result.returns)],
                "dates": result.dates,
                "totalCosts": float(result.total_costs),
            })
            return summary

        in_sample = evaluate(train, "in-sample")
        out_sample = evaluate(test, "out-of-sample")
        benchmark = None
        if "NIFTY50" in returns.columns:
            bench_result = simulate_portfolio(
                test[["NIFTY50"]], np.array([1.0]),
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
                periodic_contribution=float(getattr(request, "monthlyContribution", 0.0) or 0.0),
                rebalance_frequency="none", transaction_cost_bps=0.0,
            )
            benchmark = summarize_curve(
                pd.DatetimeIndex(test.index), bench_result.equity, bench_result.returns,
                snapshot.periods_per_year, rf, bench_result.total_contributions,
                contribution_dates=bench_result.contribution_dates,
                initial_value=float(getattr(request, "initialValue", 1_000_000.0) or 1_000_000.0),
            )
        return {
            "strategy": strategy,
            "weights": {s: float(weights[i]) for i, s in enumerate(symbols)},
            "inSample": in_sample,
            "outOfSample": out_sample,
            "benchmarkOutOfSample": benchmark,
            "trainEnd": train_end,
            "assumptions": {
                "trainStart": str(train.index[0].date()),
                "trainEnd": str(train.index[-1].date()),
                "testStart": str(test.index[0].date()),
                "testEnd": str(test.index[-1].date()),
                "riskFreeRate": rf,
                "transactionCostBps": cost,
                "noLookAhead": True,
            },
        }
