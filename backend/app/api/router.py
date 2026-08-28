"""Aggregated API router."""
from fastapi import APIRouter

from .routes import analytics, assets, optimization, portfolio, simulation, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(assets.router)
api_router.include_router(analytics.router)
api_router.include_router(portfolio.router)
api_router.include_router(optimization.router)
api_router.include_router(simulation.router)
