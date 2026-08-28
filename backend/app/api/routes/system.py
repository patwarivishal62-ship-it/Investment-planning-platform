"""System endpoints: health, data status, configuration, methodology metadata."""
from __future__ import annotations

from fastapi import APIRouter, Request

from ...core.config import get_settings
from ...core.logging import get_logger
from ...services.market_data import MarketDataService
from ...services.profile import HORIZONS, OBJECTIVES, QUESTIONS, PROFILE_BANDS

router = APIRouter(tags=["system"])
logger = get_logger("api.system")


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "provider": settings.market_data_provider,
        "version": "1.0.0",
    }


@router.get("/data/status")
async def data_status(request: Request) -> dict:
    """Mode (demo | live | cached), provider, timestamp, asset count, quality."""
    service = MarketDataService()
    try:
        status = service.status()
    except Exception as exc:
        logger.warning("status check failed: %s", exc)
        status = {
            "mode": "unavailable",
            "provider": "unknown",
            "lastUpdated": None,
            "warnings": ["Market data is temporarily unavailable."],
            "isDemo": False,
        }
    try:
        snapshot = await service.get_snapshot()
        status.update(
            {
                "assetCount": len(snapshot.symbols),
                "historyStart": snapshot.start,
                "historyEnd": snapshot.end,
                "observations": int(len(snapshot.returns)),
                "dataQuality": {
                    "score": round(snapshot.quality.score, 1),
                    "grade": snapshot.quality.grade,
                    "issues": [i.message for i in snapshot.quality.issues[:5]],
                    "quarantined": list(snapshot.quality.quarantined)[:10],
                    "coverage": snapshot.quality.coverage,
                },
            }
        )
    except Exception as exc:
        logger.warning("snapshot for status failed: %s", exc)
        status["dataQuality"] = None
    return status


@router.get("/config")
async def config() -> dict:
    """Non-secret configuration the UI needs (never includes API keys)."""
    settings = get_settings()
    return {
        "currency": "INR",
        "country": "IN",
        "riskFreeRate": settings.risk_free_rate,
        "tradingDaysPerYear": settings.trading_days_per_year,
        "defaultLookbackYears": settings.default_lookback_years,
        "defaultRebalanceFrequency": settings.default_rebalance_frequency,
        "varConfidence": settings.var_confidence,
        "defaultTransactionCostBps": settings.default_transaction_cost_bps,
        "provider": settings.market_data_provider,
        "providerConfigured": bool(settings.market_data_base_url),
    }


@router.get("/profile/questions")
async def profile_questions() -> dict:
    return {
        "questions": QUESTIONS,
        "objectives": OBJECTIVES,
        "horizons": HORIZONS,
        "bands": [{"max": upper, "label": label} for upper, label in PROFILE_BANDS],
    }
