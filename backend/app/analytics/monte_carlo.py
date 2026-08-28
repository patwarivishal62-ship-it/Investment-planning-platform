"""Monte Carlo projection -- illustrative scenarios, never a forecast.

Methods
-------
``normal``      multivariate Gaussian draws from the historical mean vector and
                covariance matrix (parametric / model-based).
``student_t``   multivariate Student-t with configurable degrees of freedom --
                fatter tails than the Gaussian, still model-based.
``bootstrap``   stationary block bootstrap of *realised* historical portfolio
                returns -- non-parametric, keeps the empirical distribution but
                cannot produce events worse than those observed.

All methods are seeded: the same seed always reproduces the same result.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["monte_carlo", "METHODS"]

METHODS = ("normal", "student_t", "bootstrap")


def monte_carlo(
    weights,
    mu_annual: np.ndarray,
    cov_annual: np.ndarray,
    initial_value: float,
    periodic_contribution: float = 0.0,
    years: float = 10.0,
    paths: int = 10_000,
    seed: int | None = 42,
    method: str = "normal",
    steps_per_year: int = 12,
    df: int = 5,
    annual_contribution_increase: float = 0.0,
    historical_returns: np.ndarray | None = None,
    block_length: int = 3,
    percentiles=(10, 25, 50, 75, 90),
) -> dict:
    """Project a distribution of future portfolio values.

    Contributions are added at the end of each step; the portfolio is assumed
    to be rebalanced back to the target weights each step. Returns are
    periodic (annual/12 by default) and drawn jointly across assets.
    """
    if method not in METHODS:
        raise ValueError(f"unknown Monte Carlo method: {method!r}")
    paths = int(max(1, paths))
    steps = int(max(1, round(float(years) * steps_per_year)))
    w = np.asarray(weights, dtype=float)
    mu = np.asarray(mu_annual, dtype=float)
    cov = np.asarray(cov_annual, dtype=float)
    rng = np.random.default_rng(seed)

    mu_p = float(w @ mu) / steps_per_year
    var_p = float(w @ cov @ w) / steps_per_year
    sigma_p = float(np.sqrt(max(var_p, 0.0)))

    if method == "bootstrap":
        if historical_returns is None or np.asarray(historical_returns).size < block_length * 2:
            raise ValueError(
                "bootstrap Monte Carlo requires the historical portfolio return series"
            )
        hist = np.asarray(historical_returns, dtype=float)
        hist = hist[np.isfinite(hist)]
        # Aggregate the observed series to the projection frequency.
        per = max(1, int(round(252 / steps_per_year)))
        if per > 1 and hist.size >= per:
            trimmed = hist[: (hist.size // per) * per]
            hist = (1.0 + trimmed.reshape(-1, per)).prod(axis=1) - 1.0
        n_blocks = int(np.ceil(steps / block_length)) + 1

    values = np.full(paths, float(initial_value), dtype=float)
    curve = np.empty((steps + 1, paths), dtype=float)
    curve[0] = values
    total_contrib = np.zeros(paths, dtype=float)

    for step in range(1, steps + 1):
        if method == "normal":
            r = rng.normal(mu_p, sigma_p, size=paths)
        elif method == "student_t":
            z = rng.standard_t(df, size=paths)
            scale = np.sqrt((df - 2.0) / df) if df > 2 else 1.0
            r = mu_p + sigma_p * z * scale
        else:
            starts = rng.integers(0, max(1, hist.size - block_length), size=paths * n_blocks)
            idx = starts.reshape(paths, n_blocks)
            offsets = np.arange(block_length)
            blocks = hist[(idx[:, :, None] + offsets[None, None, :]) % hist.size]
            sampled = blocks.reshape(paths, -1)[:, :steps]
            # Each path uses the blocks drawn for it; take this step's column.
            r = sampled[:, step - 1]

        values = values * (1.0 + r)
        contribution = float(periodic_contribution)
        if contribution and annual_contribution_increase:
            contribution *= (1.0 + float(annual_contribution_increase)) ** ((step - 1) / steps_per_year)
        values = values + contribution
        total_contrib += contribution
        curve[step] = values

    final = curve[-1]
    pcts = {f"p{p}": float(np.percentile(final, p)) for p in percentiles}
    percentile_paths = {
        f"p{p}": [float(v) for v in np.percentile(curve, p, axis=1)] for p in percentiles
    }
    years_axis = [round(i / steps_per_year, 4) for i in range(steps + 1)]

    invested = float(initial_value) + float(np.mean(total_contrib))
    return {
        "method": method,
        "paths": paths,
        "years": float(years),
        "stepsPerYear": steps_per_year,
        "seed": seed,
        "initialValue": float(initial_value),
        "periodicContribution": float(periodic_contribution),
        "totalContributions": float(np.mean(total_contrib)),
        "totalInvested": invested,
        "finalValues": pcts,
        "medianFinalValue": float(np.median(final)),
        "meanFinalValue": float(np.mean(final)),
        "probabilityOfLoss": float(np.mean(final < invested)),
        "probabilityOfDouble": float(np.mean(final >= 2 * invested)),
        "percentilePaths": percentile_paths,
        "yearsAxis": years_axis,
        "assumptions": {
            "expectedAnnualReturn": float(w @ mu),
            "annualVolatility": sigma_p * np.sqrt(steps_per_year),
            "rebalancedEveryStep": True,
            "costsAndTaxesIgnored": True,
        },
    }
