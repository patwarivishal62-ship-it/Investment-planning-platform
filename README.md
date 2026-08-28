# Multi-Asset Quantitative Investment Plan Generator

An analytical, decision-support application for multi-asset portfolio planning.

You enter objectives, capital, horizon and risk tolerance. The engine analyses historical
multi-asset data, generates and screens tens of thousands of candidate portfolios, ranks them,
and presents four to five genuinely different plans — each with return, volatility, Sharpe,
Sortino, drawdown, diversification and a plain-language explanation of *why* it looks the way
it does.

> **This is not investment advice.** It is a quantitative analysis and education tool.
> It never promises returns, never fabricates market data, and never executes trades.
> See [`app/disclaimer`](frontend/app/disclaimer/page.tsx) and the
> [Methodology](#methodology) page inside the app.

---

## Try the core journey

1. Open the app and click **Explore with Demo Data**.
2. Complete the 5-step questionnaire — capital ₹10,00,000, monthly contribution ₹20,000,
   10-year horizon, Moderate risk, Wealth Creation.
3. Five plans are generated from ~25,000 candidates.
4. Open a plan: allocation, expected return, volatility, Sharpe, Sortino, max drawdown,
   risk score, correlation matrix, efficient frontier and historical backtest.
5. **What-if** — move the allocation sliders and watch risk and return recompute live.
6. **Scenarios** — apply a hypothetical stress shock and see the impact.
7. Compare plans side by side, run a Monte Carlo projection, or validate out of sample
   with walk-forward testing.

The header pill always tells you whether the data is **Demo**, **Live** or **Cached**, with
its source and timestamp, and every individual chart carries a
`Demo data — not live market data` tag on its own face — because a chart can be screenshotted
or exported on its own. That label is rendered **server-side**, so it is present in the first
paint rather than appearing only after hydration.

---

## Architecture

```
backend/     Python · FastAPI · NumPy · pandas · SciPy   — the quantitative engine
frontend/    Next.js · TypeScript · React · Tailwind     — presentation only
```

The split is deliberate and enforced: **no financial metric is computed in the frontend**.
Every number on screen comes from a tested function in `backend/app/analytics/`.

The browser only ever talks to the Next.js server on a relative `/api/*` path, which is
proxied server-side to FastAPI. No CORS, no exposed backend port, and **API keys never reach
the browser** — they live only in the backend environment.

### Backend

| Module | Responsibility |
| --- | --- |
| `analytics/returns.py` | Simple and log returns, annualisation, CAGR |
| `analytics/risk.py` | Volatility, Sharpe, Sortino, drawdown, VaR, CVaR, Calmar, Ulcer |
| `analytics/portfolio.py` | Expected return, covariance, risk contribution, consolidation |
| `analytics/optimization.py` | Six strategies: min-variance, max-Sharpe, risk parity, max-diversification, max-return-under-risk-cap, min-CVaR |
| `analytics/correlation.py` | Pairwise and rolling correlation, nearest-PSD projection |
| `analytics/backtest.py` | Walk-forward simulator with rebalancing and costs |
| `analytics/monte_carlo.py` | Normal, Student-t and block-bootstrap projections |
| `analytics/stress.py` | Hypothetical shocks and observed historical stress windows |
| `data/` | Provider abstraction, demo (synthetic) provider, real provider, **data-quality pipeline** |
| `services/` | Market data snapshotting, portfolio analytics, recommendation engine, simulation |

### Frontend

15 routes. Design tokens live in `app/globals.css` and `tailwind.config.ts`; formatting
(₹10,00,000 lakh/crore grouping, restrained decimals) is centralised in `lib/format.ts`
so no component invents its own number style.

```
/                    Landing
/onboarding          5-step questionnaire, risk score recomputed on every answer
/recommendations     Generated plans, fit scores, scoring weights
/portfolio/[id]      Deep dive: Overview · What-if · Risk · Simulation
/dashboard           Profile summary and market overview
/compare             Side-by-side plan comparison
/optimizer           Any of six strategies under your own constraints
/analytics           Asset performance, risk, correlation, distribution, drawdown, rolling, frontier
/assets              Full 26-instrument universe with data provenance
/backtest            Backtest, rebalancing study, walk-forward out-of-sample
/stress-test         Editable hypothetical shocks + observed historical windows
/monte-carlo         Projection with method, path count and seed control
/settings            Data provider status, quality report, financial assumptions
/methodology         Plain-language explanation of every metric
/disclaimer          What this is, and what it is not
```

---

## Running locally

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env          # optional — defaults work out of the box
uvicorn app.main:app --reload --port 8000
```

API docs: <http://localhost:8000/docs>

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```

The frontend proxies `/api/*` to `http://127.0.0.1:8000`. Point it elsewhere with
`BACKEND_URL`.

### Tests

```bash
cd backend && .venv/bin/python -m pytest tests -q     # 140 tests
cd frontend && npx tsc --noEmit                       # type check
cd frontend && npx next build                          # production build
```

There is also a **runtime contract check** that replays every API call the frontend makes
and asserts that every field the components read is present — it catches "the page renders
but shows `undefined`" bugs without a browser:

```bash
cd frontend && node scripts/contract-check.mjs http://127.0.0.1:3000/api
```

---

## Data: demo, live and cached

The app is fully functional with **no API key**. In Demo Data mode every price series is
synthetic, generated from a seeded statistical model, and labelled as such on every page.

To connect a real provider, copy `.env.example` and set:

```env
MARKET_DATA_PROVIDER=real
MARKET_DATA_BASE_URL=https://your-provider.example.com
MARKET_DATA_API_KEY=your_key_here      # server-side only, never sent to the browser
RISK_FREE_RATE=0.065
DEFAULT_LOOKBACK_YEARS=10
```

The provider must expose `/assets`, `/history` and `/quote`; the contract is documented in
`docs/DATA_PROVIDERS.md`.

Three rules the platform never breaks:

1. If a live provider fails, the API returns a clear error **or** serves cached data with
   its timestamp. It never silently substitutes demo data for a configured live provider.
2. The data-quality pipeline checks for duplicate dates, gaps, zero/negative prices, stale
   prices, calendar and currency mismatches, and survivorship signals. Failing assets are
   **quarantined with a reason and excluded** — never forward-filled or interpolated.
3. Nothing is ever presented as live market data when it is not.

---

## Methodology

Every metric is explained in plain language, with the technical detail one click away, on
the in-app **Methodology** page. Highlights:

- **Time-weighted vs money-weighted returns are never conflated.** `cagr` and `totalReturn`
  compound periodic returns only, so contributions can never inflate performance.
  `endValue`, `invested` and `moneyWeightedReturn` describe the *account*. Drawdown is
  measured on the time-weighted curve, because fresh cash masks falls.
- **Historical vs model-based figures are labelled.** Historical VaR/CVaR are non-parametric;
  parametric variants are marked MODEL-BASED and never presented interchangeably.
- **Walk-forward validation is genuinely out of sample.** Weights are fitted only on the
  training window, then frozen and applied to a strictly later test window. The API asserts
  the split. In this demo data, an optimiser fitted on 2016–2023 produced 21.6% in sample and
  0.04% out of sample — the tool shows that gap rather than hiding it.
- **Explanations are generated, not templated.** Each plan explains its return driver, its
  risk reducer (with correlation-to-portfolio), its diversification, its main risk, and a
  caveat — all computed from the actual holdings.

---

## Known limitations

- **No persistence layer yet.** The engine is stateless: market data snapshots are held in
  memory and user profiles are stored in the browser's `localStorage`. PostgreSQL +
  SQLAlchemy is the intended home for saved profiles, plan history and provider audit logs,
  and the empty `database/` directory is reserved for it. Nothing in the current feature set
  depends on it.
- Optimised portfolios are sensitive to inputs; small changes in sample period can shift
  allocations materially.
- Historical correlations are not stable and tend to converge toward 1 in crises.
- Backtests model transaction costs as a configurable assumption. **Taxes, slippage and
  market impact are not modelled** — an explicit limitation, not an oversight.
- Monte Carlo projections assume a return distribution; real markets produce moves no model
  here captures. Results are illustrative scenarios, not forecasts.
- The Platform Risk Score is a transparent 0–100 composite defined by this application.
  It is **not** a SEBI riskometer or any regulated rating.
- Demo data is synthetic and Indian-market-shaped by default; other markets and currencies
  are supported by the architecture but no alternative universe ships yet.
- Derivatives are analytical only. Nothing here is tradable through this application.

---

## Disclaimer

Historical performance does not indicate future performance. Expected returns are estimates
derived from historical data and explicit assumptions — not promises. Correlations change.
Model assumptions can fail. This tool does not take your full financial situation into
account and is not personalised, regulated investment advice. Consult a qualified
professional before acting on any output.
