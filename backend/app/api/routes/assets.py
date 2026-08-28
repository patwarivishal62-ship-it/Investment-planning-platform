"""Asset universe endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ...core.logging import get_logger
from ...data.providers.base import DataProviderError
from ...services.market_data import MarketDataService

router = APIRouter(prefix="/assets", tags=["assets"])
logger = get_logger("api.assets")


@router.get("")
async def list_assets() -> list[dict]:
    service = MarketDataService()
    try:
        return await service.get_assets()
    except DataProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("failed to list assets")
        raise HTTPException(status_code=500, detail="Unable to load the asset universe.") from exc


@router.get("/{symbol}")
async def get_asset(symbol: str) -> dict:
    service = MarketDataService()
    try:
        assets = await service.get_assets()
    except DataProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    match = next((a for a in assets if a["symbol"] == symbol), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    return match


@router.get("/{symbol}/history")
async def asset_history(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> dict:
    service = MarketDataService()
    try:
        snapshot = await service.get_snapshot()
        start = start or date.fromisoformat(snapshot.start)
        end = end or date.fromisoformat(snapshot.end)
        rows = await service.get_history(symbol, start, end)
    except DataProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No price history available for {symbol} in the selected range.",
        )
    return {"symbol": symbol, "start": str(start), "end": str(end), "prices": rows}
