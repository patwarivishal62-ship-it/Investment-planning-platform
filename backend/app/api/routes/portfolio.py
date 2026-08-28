"""Portfolio analysis, what-if simulation and risk decomposition."""
from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import (
    AnalysisRequest,
    DiversificationRequest,
    RiskContributionRequest,
    WhatIfRequest,
)
from ...services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyze")
async def analyze(request: AnalysisRequest) -> dict:
    """Full metric bundle for an arbitrary allocation."""
    service = PortfolioService()
    return await service.analyze(request)


@router.post("/what-if")
async def what_if(request: WhatIfRequest) -> dict:
    """Instant recomputation when the user drags an allocation slider."""
    service = PortfolioService()
    return await service.what_if(request)


@router.post("/risk-contribution")
async def risk_contribution(request: RiskContributionRequest) -> dict:
    service = PortfolioService()
    return await service.risk_contribution(request)


@router.post("/diversification")
async def diversification(request: DiversificationRequest) -> dict:
    """'How diversified is my portfolio?' -- step-by-step hedging comparison."""
    service = PortfolioService()
    return await service.diversification_ladder(request)


@router.post("/advanced")
async def advanced(request: AnalysisRequest) -> dict:
    service = PortfolioService()
    return await service.advanced_metrics(request)
