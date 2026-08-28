# Market data provider contract

The backend never speaks to a market data vendor directly from a route handler. All access
goes through `app/data/`, which defines a single abstract interface with two implementations:

| Provider | Class | Purpose |
| --- | --- | --- |
| `demo` | `DemoMarketDataProvider` | Seeded synthetic series. **Default.** No credentials, no network. |
| `real` | `RealMarketDataProvider` | Talks to an HTTP provider over the contract below. |

A third mode, **`cached`**, is not a provider — it is a state. When a live provider fails but a
previous snapshot exists, the API serves the cached snapshot **with its original timestamp**
and marks the mode as `cached`. It never relabels cached or synthetic data as live.

---

## The interface

Any provider must implement:

```python
class MarketDataProvider(Protocol):
    def list_assets(self) -> list[Asset]: ...
    def get_history(self, symbols: list[str], start, end) -> pd.DataFrame: ...
    def get_quote(self, symbol: str) -> Quote: ...
    @property
    def provider_name(self) -> str: ...
```

`list_assets` returns instrument metadata (symbol, name, asset class, sector, currency,
liquidity score). `get_history` returns a `DataFrame` of **adjusted close prices**, indexed by
date, one column per symbol. `get_quote` returns the latest price and its timestamp.

---

## HTTP contract for `real`

Set `MARKET_DATA_PROVIDER=real` and `MARKET_DATA_BASE_URL`. The provider calls three endpoints.
Responses are JSON.

### `GET /assets`

```json
{
  "assets": [
    {
      "symbol": "NIFTY50",
      "name": "Nifty 50",
      "assetClass": "equity",
      "sector": "Broad Market",
      "currency": "INR",
      "liquidityScore": 1.0
    }
  ]
}
```

`assetClass` must be one of: `equity`, `bond`, `gold`, `silver`, `commodity`,
`international_equity`, `reit`, `cash`. Unknown classes are rejected rather than guessed at.

### `GET /history`

Query parameters: `symbols` (comma-separated), `start`, `end` (`YYYY-MM-DD`).

```json
{
  "history": [
    { "symbol": "NIFTY50", "date": "2016-08-29", "close": 8631.0 },
    { "symbol": "NIFTY50", "date": "2016-08-30", "close": 8620.5 }
  ]
}
```

A long format is used deliberately: it tolerates instruments with different listing dates
and different calendars, which a wide format cannot express without inventing values.

### `GET /quote`

```json
{ "symbol": "NIFTY50", "price": 24812.0, "asOf": "2026-08-28T15:30:00+05:30" }
```

### Authentication

`MARKET_DATA_API_KEY` is sent as a `Bearer` token. **It is read only in the backend process
and is never exposed to the browser.** The frontend has no code path that can see it.

---

## Caching

Successful responses are cached to disk under the cache directory from settings. The cache key
is the request path **with its parameters**; when no parameters are sent the bare path is the
key. Cache hits are logged and reported through `/api/data/status`.

If a live request fails and no cache entry exists, the API returns `503` with
`code: "market_data_unavailable"` and actionable suggestions. **It does not fall back to demo
data** — silently swapping synthetic prices into a live-configured system is exactly the kind
of substitution this platform refuses to make.

---

## Data quality pipeline

Before any analysis, `app/data/quality.py` runs a battery of checks on the assembled panel:

| Check | Severity |
| --- | --- |
| Duplicate dates | blocking |
| Unsorted dates | repaired deterministically, reported |
| Missing sessions / gaps | warning |
| Missing prices | blocking (asset quarantined) |
| Zero or negative prices | blocking |
| Non-finite values | blocking |
| Extreme unexplained jumps | warning |
| Stale (unchanged) prices | warning |
| Calendar mismatch across assets | warning |
| Currency mismatch | blocking |
| Late listing / early termination | informational (survivorship signal) |

Assets failing a blocking check are **quarantined with a reason and excluded from the
analysis**. The API reports which symbols were dropped and why. The pipeline never
forward-fills and never interpolates.

A composite 0–100 score with a grade is produced and surfaced on the Settings page and beside
every analysis.

---

## Adding a new provider

1. Subclass `MarketDataProvider` in `app/data/`.
2. Implement the three methods; raise `DataProviderError` with an actionable message on failure.
3. Register it in the provider factory keyed by `MARKET_DATA_PROVIDER`.
4. Add tests in `backend/tests/test_providers.py` using a stub HTTP server — no live network.

Nothing else in the codebase needs to change. The analytics, optimisation, simulation and
recommendation layers all consume the provider interface, so a new vendor cannot alter any
calculation.
