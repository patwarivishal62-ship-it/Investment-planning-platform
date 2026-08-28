"""Provider selection. The rest of the app only ever sees the interface type."""
from __future__ import annotations

from functools import lru_cache

from ...core.config import Settings, get_settings
from .base import DataProviderError, MarketDataProvider
from .demo import DemoMarketDataProvider


def build_provider(settings: Settings | None = None) -> MarketDataProvider:
    settings = settings or get_settings()
    if settings.market_data_provider == "real":
        try:
            from .real import RealMarketDataProvider

            return RealMarketDataProvider(
                base_url=settings.market_data_base_url,
                api_key=settings.market_data_api_key,
                timeout=settings.market_data_timeout_seconds,
                cache_dir=settings.market_data_cache_dir,
            )
        except DataProviderError as exc:
            # A misconfigured live provider must not silently return demo data.
            raise DataProviderError(
                f"{exc} The application will not substitute demo data for a configured "
                "live provider. Set MARKET_DATA_PROVIDER=demo to explore with synthetic data."
            ) from exc
    return DemoMarketDataProvider(seed=20240501)


@lru_cache
def get_provider() -> MarketDataProvider:
    return build_provider()
