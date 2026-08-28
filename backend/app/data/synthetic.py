"""Deterministic synthetic market data for DEMO mode.

These series are *not* real market data and are never presented as such. They
are generated from a seeded factor model so that:

  * correlations between assets are economically plausible (equities move
    together, bonds are close to independent, gold is only loosely linked);
  * fat tails and clustered stress periods produce realistic drawdowns;
  * the same seed always produces the same series, so tests are reproducible.

Every caller must surface the DEMO label to the end user.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .universe import UNIVERSE, AssetMeta

__all__ = ["generate_demo_prices", "FACTORS", "DemoDataWarning"]

DemoDataWarning = "DEMO DATA - SYNTHETIC, NOT LIVE OR HISTORICAL MARKET DATA"

FACTORS = [
    "in_equity", "in_sizemid", "in_sizesmall",
    "sector_bank", "sector_it", "sector_pharma", "sector_fmcg", "sector_auto", "sector_infra",
    "rates", "credit", "gold", "silver", "commodity", "crude", "copper", "natgas",
    "global_equity", "us_tech", "em_equity", "usdinr", "reit",
]

# Factors that get amplified during a stress regime (see _regime_path).
STRESS_FACTORS = {"in_equity", "global_equity", "us_tech", "em_equity", "credit", "in_sizemid", "in_sizesmall"}
EQUITY_FACTORS = {"in_equity", "global_equity", "us_tech", "em_equity"}


@dataclass
class DemoParams:
    seed: int = 20240501
    degrees_of_freedom: float = 5.0      # fat tails
    stress_probability: float = 0.005    # daily chance of entering a stress regime
    stress_half_life: float = 18.0       # expected stress duration in days
    stress_multiplier: float = 1.8
    stress_drift_penalty: float = 0.0012  # extra negative daily drift while stressed
    trading_days: int = 252


def _unit_t_shocks(rng: np.random.Generator, shape: tuple[int, int], df: float) -> np.ndarray:
    """Student-t shocks scaled to unit variance (fat tails, finite variance)."""
    z = rng.standard_t(df, size=shape)
    return z / np.sqrt(df / (df - 2.0)) if df > 2 else z


def _regime_path(rng: np.random.Generator, n: int, params: DemoParams) -> np.ndarray:
    """Two-state Markov chain: 0 = calm, 1 = stress. Produces clustered selloffs."""
    state = np.zeros(n, dtype=bool)
    in_stress = False
    p_exit = 1.0 / max(params.stress_half_life, 1.0)
    for t in range(n):
        if in_stress:
            if rng.random() < p_exit:
                in_stress = False
        elif rng.random() < params.stress_probability:
            in_stress = True
        state[t] = in_stress
    return state


def generate_demo_prices(
    symbols: list[str],
    start: str = "2015-01-01",
    end: str | None = None,
    params: DemoParams | None = None,
    base_prices: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Generate a deterministic price frame indexed by business days."""
    params = params or DemoParams()
    end = end or pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
    dates = pd.bdate_range(start=start, end=end)
    if len(dates) < 30:
        raise ValueError("demo generation needs at least 30 business days of range")

    metas = {a.symbol: a for a in UNIVERSE if a.symbol in set(symbols)}
    missing = set(symbols) - set(metas)
    if missing:
        raise KeyError(f"unknown demo symbols: {sorted(missing)}")

    n = len(dates)
    k = len(FACTORS)
    index_of_factor = {f: i for i, f in enumerate(FACTORS)}

    # The factor shocks are SHARED across the whole universe -- that is what
    # creates the correlation structure. Only the idiosyncratic term is drawn
    # per symbol, and both streams derive deterministically from the master seed.
    factor_rng = np.random.default_rng(params.seed)
    shocks = _unit_t_shocks(factor_rng, (n, k), params.degrees_of_freedom) / np.sqrt(params.trading_days)
    regime_rng = np.random.default_rng(params.seed + 7919)
    regime = _regime_path(regime_rng, n, params)

    factor_frame: dict[str, np.ndarray] = {}
    for sym in symbols:
        meta: AssetMeta = metas[sym]
        idio_rng = np.random.default_rng(params.seed + _stable_hash(sym))
        idio = _unit_t_shocks(idio_rng, (n, 1), params.degrees_of_freedom) / np.sqrt(params.trading_days)

        explained = float(sum(meta.demoLoadings.values()))
        idio_share = max(0.0, 1.0 - explained)
        daily = meta.demoDrift / params.trading_days + np.zeros(n)
        for factor, share in meta.demoLoadings.items():
            col = shocks[:, index_of_factor[factor]]
            if factor in STRESS_FACTORS:
                col = col * np.where(regime, params.stress_multiplier, 1.0)
                if factor in EQUITY_FACTORS:
                    daily = daily - np.where(regime, params.stress_drift_penalty, 0.0)
            daily = daily + meta.demoVol * np.sqrt(share) * col
        daily = daily + meta.demoVol * np.sqrt(idio_share) * idio[:, 0]

        # Idiosyncratic vol also expands in stress (correlations rise together).
        daily = np.where(regime, daily * 1.15, daily)

        # Calibration: rescale each series so its realised mean and volatility
        # match the configured targets exactly. Scaling by a positive constant
        # and shifting the mean leaves the correlation structure untouched, so
        # we keep the factor-driven co-movement, the fat tails and the clustered
        # stress periods -- but the demo inputs become meaningful numbers.
        daily = _calibrate(daily, meta.demoDrift / params.trading_days,
                           meta.demoVol / np.sqrt(params.trading_days))

        # Guard: a price can never go non-positive.
        daily = np.clip(daily, -0.35, 0.35)
        factor_frame[sym] = daily

    returns = pd.DataFrame(factor_frame, index=dates)
    prices = 100.0 * (1.0 + returns).cumprod()
    if base_prices:
        for sym, base in base_prices.items():
            if sym in prices.columns:
                prices[sym] = prices[sym] / float(prices[sym].iloc[0]) * float(base)
    prices.index.name = "date"
    return prices


def _stable_hash(text: str) -> int:
    """FNV-1a -- stable across processes (unlike Python's salted hash())."""
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _calibrate(daily: np.ndarray, target_mean: float, target_std: float) -> np.ndarray:
    """Affine-transform a return series to an exact mean and standard deviation.

    Correlations are invariant under positive scaling and translation, so this
    preserves the cross-asset structure produced by the factor model.
    """
    observed_std = float(np.std(daily, ddof=1))
    observed_mean = float(np.mean(daily))
    if observed_std <= 0 or not np.isfinite(observed_std):
        return np.full_like(daily, target_mean)
    return (daily - observed_mean) / observed_std * target_std + target_mean
