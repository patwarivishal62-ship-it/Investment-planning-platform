"""Optimization, efficient frontier and the recommendation engine.

Recommend/optimize are the expensive endpoints, so they are rate limited.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request

from ...core.logging import get_logger
from ...schemas.requests import EfficientFrontierRequest, OptimizeRequest, RecommendRequest
from ...services.portfolio import PortfolioService
from ...services.recommendation import RecommendationService

router = APIRouter(tags=["optimization"])
logger = get_logger("api.optimization")

# --------------------------------------------------------------- rate limiting
# Simple in-memory sliding window. Sufficient for a single-process deployment;
# swap for Redis if the service is ever run multi-instance.
_CALLS: dict[str, deque] = defaultdict(deque)
LIMIT = 30
WINDOW_SECONDS = 60


def _rate_limit(request: Request, key: str) -> None:
    now = time.monotonic()
    bucket = _CALLS[key]
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= LIMIT:
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many optimisation requests. Please wait a moment before running "
                "another analysis."
            ),
        )
    bucket.append(now)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "local"


@router.post("/portfolio/optimize")
async def optimize(request: OptimizeRequest, raw: Request) -> dict:
    _rate_limit(raw, f"optimize:{_client_key(raw)}")
    service = PortfolioService()
    return await service.optimize(request)


@router.post("/portfolio/recommend")
async def recommend(request: RecommendRequest, raw: Request) -> dict:
    """Generate 4-5 ranked, genuinely different investment plans."""
    _rate_limit(raw, f"recommend:{_client_key(raw)}")
    service = RecommendationService()
    result = await service.recommend(request)
    logger.info(
        "recommendation produced plans=%s candidates=%s objective=%s",
        [p["name"] for p in result["plans"]],
        result["candidateCount"],
        request.objective,
    )
    return result


@router.post("/efficient-frontier")
async def frontier(request: EfficientFrontierRequest, raw: Request) -> dict:
    _rate_limit(raw, f"frontier:{_client_key(raw)}")
    service = PortfolioService()
    return await service.efficient_frontier(request)
