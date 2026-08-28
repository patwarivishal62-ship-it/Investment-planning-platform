"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.router import api_router
from .core.config import get_settings
from .core.logging import get_logger, setup_logging
from .data.providers.base import DataProviderError
from .optimization.constraints import OptimizationError
from .schemas.responses import ErrorPayload

setup_logging()
logger = get_logger("app")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .services.market_data import MarketDataService

    logger.info(
        "starting backend provider=%s risk_free_rate=%.4f trading_days=%d",
        settings.market_data_provider,
        settings.risk_free_rate,
        settings.trading_days_per_year,
    )
    try:
        service = MarketDataService()
        snapshot = await service.get_snapshot()
        logger.info(
            "market data ready mode=%s assets=%d range=%s..%s quality=%.1f",
            service.status().get("mode"),
            len(snapshot.symbols),
            snapshot.start,
            snapshot.end,
            snapshot.quality.score,
        )
    except Exception as exc:
        logger.warning("market data unavailable at startup: %s", exc)
    yield


app = FastAPI(
    title="Quantitative Investment Plan Generator",
    version="1.0.0",
    description=(
        "Quantitative portfolio analysis and educational decision support. "
        "Analytical tool only: nothing here is personalised regulated investment advice "
        "and no return is guaranteed."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OptimizationError)
async def optimization_error_handler(request: Request, exc: OptimizationError):
    """No-feasible-portfolio -> actionable suggestions, never a fabricated plan."""
    logger.warning("optimization infeasible: %s", exc)
    return JSONResponse(
        status_code=422,
        content=ErrorPayload(
            error=str(exc),
            code="no_feasible_portfolio",
            suggestions=exc.suggestions,
            detail=exc.detail,
        ).model_dump(),
    )


@app.exception_handler(DataProviderError)
async def data_provider_error_handler(request: Request, exc: DataProviderError):
    logger.warning("data provider error: %s", exc)
    return JSONResponse(
        status_code=503,
        content=ErrorPayload(
            error=str(exc) or "Market data is temporarily unavailable.",
            code="market_data_unavailable",
            suggestions=[
                "Retry in a moment.",
                "Switch to Demo Data in Settings to keep exploring with synthetic data.",
            ],
        ).model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content=ErrorPayload(error=str(exc), code="invalid_request").model_dump(),
    )


app.include_router(api_router)

