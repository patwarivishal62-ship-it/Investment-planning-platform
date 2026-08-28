"""Validated request models. All API input is checked here -- not in the maths."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OBJECTIVE_LITERAL = Literal[
    "capital_preservation", "balanced_growth", "wealth_creation",
    "income", "inflation_protection", "maximum_growth",
]
REBALANCE_LITERAL = Literal["none", "monthly", "quarterly", "semiannual", "annual", "threshold"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class SymbolRangeRequest(_Base):
    symbols: list[str] | None = None
    start: date | None = None
    end: date | None = None


class ConstraintsMixin(BaseModel):
    """Shared allocation constraints (spec section 6)."""

    minWeight: float = Field(0.0, ge=0.0, le=1.0)
    maxWeight: float = Field(1.0, ge=0.0, le=1.0)
    assetBounds: dict[str, list[float]] | None = None
    classBounds: dict[str, list[float]] | None = None
    sectorBounds: dict[str, list[float]] | None = None
    excluded: list[str] | None = None
    maxVolatility: float | None = Field(None, ge=0.0, le=2.0)
    maxDrawdown: float | None = Field(None, ge=0.0, le=1.0)
    minReturn: float | None = Field(None, ge=-1.0, le=5.0)
    maxAssets: int | None = Field(None, ge=1, le=60)

    @field_validator("assetBounds", "classBounds", "sectorBounds")
    @classmethod
    def _check_bounds(cls, value):
        if value is None:
            return value
        for key, bounds in value.items():
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError(f"bounds for '{key}' must be a [min, max] pair")
            lo, hi = bounds
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f"bounds for '{key}' have min > max")
            for v in bounds:
                if v is not None and not 0.0 <= v <= 1.0:
                    raise ValueError(f"bounds for '{key}' must be between 0 and 1")
        return value


class WeightedRequest(SymbolRangeRequest):
    weights: dict[str, float]
    riskFreeRate: float | None = Field(None, ge=0.0, le=0.5)

    @field_validator("weights")
    @classmethod
    def _check_weights(cls, value: dict[str, float]):
        if not value:
            raise ValueError("at least one weight is required")
        for symbol, weight in value.items():
            if weight < -1e-9:
                raise ValueError(f"weight for '{symbol}' cannot be negative")
        total = sum(value.values())
        if total <= 0:
            raise ValueError("weights must sum to a positive number")
        return {k: v / total for k, v in value.items()}


class AnalysisRequest(WeightedRequest):
    pass


class WhatIfRequest(WeightedRequest):
    pass


class OptimizeRequest(SymbolRangeRequest, ConstraintsMixin):
    strategies: list[str] | None = None
    riskFreeRate: float | None = Field(None, ge=0.0, le=0.5)
    targetVolatility: float | None = Field(None, ge=0.0, le=2.0)
    targetReturn: float | None = Field(None, ge=-1.0, le=5.0)

    @field_validator("strategies")
    @classmethod
    def _check_strategies(cls, value):
        allowed = {"min_variance", "max_sharpe", "max_return_for_risk",
                   "risk_parity", "max_diversification", "min_cvar"}
        if value is None:
            return value
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown strategies: {sorted(unknown)}")
        return value


class EfficientFrontierRequest(SymbolRangeRequest, ConstraintsMixin):
    points: int = Field(40, ge=5, le=200)
    riskFreeRate: float | None = Field(None, ge=0.0, le=0.5)


class CorrelationRequest(SymbolRangeRequest):
    window: int | None = Field(None, ge=5, le=10000)
    rollingSymbol: str | None = None
    rollingSymbolB: str | None = None
    rollingWindow: int = Field(90, ge=5, le=1000)


class RiskContributionRequest(WeightedRequest):
    pass


class DiversificationRequest(WeightedRequest):
    maxWeight: float = Field(1.0, ge=0.0, le=1.0)


class RecommendRequest(SymbolRangeRequest, ConstraintsMixin):
    capital: float = Field(1_000_000.0, ge=0.0, le=1e12)
    monthlyContribution: float = Field(0.0, ge=0.0, le=1e10)
    annualContributionIncrease: float = Field(0.0, ge=0.0, le=1.0)
    horizonYears: float = Field(10.0, ge=0.5, le=50.0)
    riskScore: float = Field(55.0, ge=0.0, le=100.0)
    objective: OBJECTIVE_LITERAL = "balanced_growth"
    secondaryObjective: OBJECTIVE_LITERAL | None = None
    rebalanceFrequency: REBALANCE_LITERAL = "quarterly"
    transactionCostBps: float | None = Field(None, ge=0.0, le=1000.0)
    candidateCount: int | None = Field(None, ge=100, le=200_000)
    maxPositions: int = Field(12, ge=2, le=40)
    minHoldingWeight: float = Field(0.02, ge=0.0, le=0.25)
    seed: int | None = 20240101
    scoringWeights: dict[str, float] | None = None

    @field_validator("scoringWeights")
    @classmethod
    def _check_weights(cls, value):
        if value is None:
            return value
        allowed = {"riskAdjustedReturn", "downsideRisk", "diversification",
                   "drawdown", "objectiveAlignment", "liquidity"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown scoring dimensions: {sorted(unknown)}")
        return value


class BacktestRequest(WeightedRequest):
    initialValue: float = Field(1_000_000.0, ge=0.0, le=1e12)
    monthlyContribution: float = Field(0.0, ge=0.0, le=1e10)
    contributionFrequency: Literal["monthly", "quarterly", "annual"] = "monthly"
    rebalanceFrequency: REBALANCE_LITERAL = "quarterly"
    rebalanceThreshold: float = Field(0.10, ge=0.0, le=1.0)
    transactionCostBps: float | None = Field(None, ge=0.0, le=1000.0)


class RebalanceCompareRequest(BacktestRequest):
    pass


class MonteCarloRequest(WeightedRequest):
    initialValue: float = Field(1_000_000.0, ge=0.0, le=1e12)
    monthlyContribution: float = Field(0.0, ge=0.0, le=1e10)
    annualContributionIncrease: float = Field(0.0, ge=0.0, le=1.0)
    years: float = Field(10.0, ge=0.5, le=60.0)
    paths: int = Field(10_000, ge=100, le=200_000)
    method: Literal["normal", "student_t", "bootstrap"] = "normal"
    stepsPerYear: int = Field(12, ge=1, le=252)
    seed: int | None = 42


class StressTestRequest(WeightedRequest):
    portfolioValue: float = Field(1_000_000.0, ge=0.0, le=1e12)
    scenarios: list[str] | None = None
    customShocks: list[dict] | None = None
    windowDays: int = Field(60, ge=5, le=1000)
    historicalWindows: int = Field(5, ge=1, le=20)


class WalkForwardRequest(SymbolRangeRequest, ConstraintsMixin):
    trainEnd: date
    strategy: str = "max_sharpe"
    riskFreeRate: float | None = Field(None, ge=0.0, le=0.5)
    targetVolatility: float | None = Field(None, ge=0.0, le=2.0)
    initialValue: float = Field(1_000_000.0, ge=0.0, le=1e12)
    monthlyContribution: float = Field(0.0, ge=0.0, le=1e10)
    rebalanceFrequency: REBALANCE_LITERAL = "quarterly"
    transactionCostBps: float | None = Field(None, ge=0.0, le=1000.0)


class RiskQuestionnaireRequest(_Base):
    answers: dict[str, str]


class AssetAnalyticsRequest(SymbolRangeRequest):
    riskFreeRate: float | None = Field(None, ge=0.0, le=0.5)
