"""Deterministic fixtures shared by the analytics tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def simple_prices() -> np.ndarray:
    """Hand-checkable price path: +10%, -10%, +10%."""
    return np.array([100.0, 110.0, 99.0, 108.9])


@pytest.fixture
def simple_returns_series() -> np.ndarray:
    return np.array([0.10, -0.10, 0.10])


@pytest.fixture
def equity_curve() -> np.ndarray:
    """100 -> 120 -> 60 -> 90 -> 130 (max drawdown -50%, then recovery)."""
    return np.array([100.0, 120.0, 60.0, 90.0, 130.0])


@pytest.fixture
def two_asset_prices() -> pd.DataFrame:
    """Two assets with a known, hand-computable covariance structure."""
    dates = pd.bdate_range("2020-01-01", periods=60)
    rng = np.random.default_rng(7)
    eq = 100.0 * np.cumprod(1.0 + rng.normal(0.0006, 0.012, len(dates)))
    bond = 100.0 * np.cumprod(1.0 + rng.normal(0.0002, 0.003, len(dates)))
    return pd.DataFrame({"EQ": eq, "BOND": bond}, index=dates)


@pytest.fixture
def diagonal_cov() -> np.ndarray:
    return np.array([[0.04, 0.0], [0.0, 0.01]])


@pytest.fixture
def diagonal_mu() -> np.ndarray:
    return np.array([0.12, 0.05])


@pytest.fixture
def demo_universe_prices() -> pd.DataFrame:
    """Small, fully deterministic synthetic universe (faster than the full one)."""
    from app.data.synthetic import DemoParams, generate_demo_prices

    symbols = ["NIFTY50", "NIFTYIT", "GOLD", "GSEC10Y", "US_EQUITY", "CASH"]
    return generate_demo_prices(
        symbols,
        start="2016-01-01",
        end="2024-12-31",
        params=DemoParams(seed=12345),
    )
