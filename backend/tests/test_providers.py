import asyncio

import pandas as pd
import pytest

from app.data.providers.base import DataProviderError
from app.data.providers.demo import DemoMarketDataProvider
from app.data.providers.real import RealMarketDataProvider
from app.data.providers.registry import build_provider
from app.core.config import Settings


def test_demo_provider_is_deterministic():
    a = DemoMarketDataProvider(seed=5, start="2020-01-01", end="2022-01-01").matrix()
    b = DemoMarketDataProvider(seed=5, start="2020-01-01", end="2022-01-01").matrix()
    pd.testing.assert_frame_equal(a, b)


def test_demo_provider_status_is_labelled_demo():
    provider = DemoMarketDataProvider(start="2020-01-01", end="2021-01-01")
    status = provider.status()
    assert status.mode == "demo"
    assert any("DEMO DATA" in w for w in status.warnings)


def test_demo_provider_rejects_unknown_symbol():
    provider = DemoMarketDataProvider(start="2020-01-01", end="2021-01-01")
    with pytest.raises(DataProviderError):
        asyncio.run(provider.get_latest_price("NOT_A_SYMBOL"))


def test_demo_prices_are_positive_and_dense():
    frame = DemoMarketDataProvider(start="2020-01-01", end="2023-01-01").matrix()
    assert (frame > 0).all().all()
    assert frame.isna().sum().sum() == 0
    assert len(frame) > 700


def test_registry_returns_demo_by_default():
    provider = build_provider(Settings(market_data_provider="demo"))
    assert provider.mode == "demo"


def test_real_provider_requires_base_url():
    with pytest.raises(DataProviderError):
        RealMarketDataProvider(base_url="")


def test_real_provider_marks_cached_mode_on_failure(monkeypatch, tmp_path):
    import app.data.providers.real as real_module

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(real_module.httpx, "AsyncClient", FailingClient)
    provider = RealMarketDataProvider(base_url="http://example.invalid",
                                      cache_dir=str(tmp_path / "cache-a"))
    # Prime the cache, then break the transport and confirm we serve cached data.
    provider._write_cache("/assets", [{"symbol": "X", "name": "X", "assetClass": "equity"}])
    payload, from_cache = asyncio.run(provider._get("/assets"))
    assert from_cache is True
    assert payload[0]["symbol"] == "X"
    assert provider.status().mode == "cached"


def test_real_provider_raises_when_no_cache_available(monkeypatch, tmp_path):
    import app.data.providers.real as real_module

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(real_module.httpx, "AsyncClient", FailingClient)
    provider = RealMarketDataProvider(base_url="http://example.invalid",
                                      cache_dir=str(tmp_path / "cache-b"))
    with pytest.raises(DataProviderError):
        asyncio.run(provider.get_assets())
