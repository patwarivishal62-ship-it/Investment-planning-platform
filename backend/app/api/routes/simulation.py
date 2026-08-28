"""Backtesting, rebalancing studies, Monte Carlo, stress tests, walk-forward."""
from __future__ import annotations

from fastapi import APIRouter, Request

from ...schemas.requests import (
    BacktestRequest,
    MonteCarloRequest,
    RebalanceCompareRequest,
    RiskQuestionnaireRequest,
    StressTestRequest,
    WalkForwardRequest,
)
from ...services.profile import risk_profile
from ...services.simulation import SimulationService

router = APIRouter(tags=["simulation"])


@router.post("/backtest")
async def backtest(request: BacktestRequest) -> dict:
    service = SimulationService()
    return await service.backtest(request)


@router.post("/backtest/rebalance")
async def rebalance_compare(request: RebalanceCompareRequest) -> dict:
    service = SimulationService()
    return await service.rebalance_compare(request)


@router.post("/backtest/walk-forward")
async def walk_forward(request: WalkForwardRequest) -> dict:
    service = SimulationService()
    return await service.walk_forward(request)


@router.post("/monte-carlo")
async def monte_carlo(request: MonteCarloRequest, raw: Request) -> dict:
    service = SimulationService()
    return await service.monte_carlo(request)


@router.post("/stress-test")
async def stress_test(request: StressTestRequest) -> dict:
    service = SimulationService()
    return await service.stress_test(request)


@router.post("/profile/risk-score")
async def risk_score(request: RiskQuestionnaireRequest) -> dict:
    try:
        return risk_profile(request.answers)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc
