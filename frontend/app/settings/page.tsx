"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks/useApi";
import { formatDateTime, formatPercent } from "@/lib/format";
import type { DataStatus } from "@/types";

/**
 * Data & API settings. The frontend never holds or displays a provider API key:
 * credentials live only in the backend environment (see .env.example).
 */
export default function SettingsPage() {
  const { data: status, error, loading, reload } = useApi<DataStatus>(() => api.status(), []);
  const { data: config } = useApi(() => api.config(), []);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Data & settings</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Provider status, data quality and the financial assumptions the engine is currently using.
        </p>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 py-10 text-sm text-ink-muted">
          <Spinner /> Loading status…
        </div>
      ) : null}
      {error ? <ErrorState message={error.message} onRetry={reload} /> : null}

      {status ? (
        <Card>
          <CardHeader
            title="Market data provider"
            subtitle="The application works identically against demo or live data."
            action={
              <span
                className={
                  status.mode === "live"
                    ? "rounded-md border border-teal-200 bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-800"
                    : status.mode === "cached"
                      ? "rounded-md border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-800"
                      : "rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800"
                }
              >
                {status.mode}
              </span>
            }
          />
          <CardBody className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Provider" value={status.provider} />
            <Stat label="Last updated" value={formatDateTime(status.lastUpdated)} />
            <Stat label="Assets" value={String(status.assetCount ?? "—")} />
            <Stat
              label="History"
              value={
                status.historyStart && status.historyEnd
                  ? `${status.historyStart} → ${status.historyEnd}`
                  : "—"
              }
            />
          </CardBody>
          {status.warnings?.length ? (
            <div className="border-t border-line px-4 py-4 sm:px-6">
              <ul className="space-y-1.5">
                {status.warnings.map((warning) => (
                  <li key={warning} className="flex gap-2 text-xs leading-relaxed text-ink-muted">
                    <span aria-hidden className="text-ink-subtle">•</span>
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>
      ) : null}

      {status?.dataQuality ? (
        <Card>
          <CardHeader
            title="Data quality"
            subtitle="Evaluated before every analysis by the data-quality pipeline."
            action={<Badge tone={status.dataQuality.score >= 90 ? "positive" : "caution"}>{status.dataQuality.grade}</Badge>}
          />
          <CardBody className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <Stat label="Score" value={`${status.dataQuality.score}/100`} />
              <Stat
                label="Sessions"
                value={String(status.dataQuality.coverage?.sessions ?? "—")}
                sub={`${status.dataQuality.coverage?.symbols ?? "—"} symbols`}
              />
              <Stat
                label="Missing cells"
                value={String(status.dataQuality.coverage?.missingCells ?? 0)}
                sub={`of ${status.dataQuality.coverage?.totalCells ?? 0}`}
              />
            </div>
            {status.dataQuality.issues?.length ? (
              <div>
                <p className="label mb-1.5">Issues detected</p>
                <ul className="space-y-1">
                  {status.dataQuality.issues.map((issue) => (
                    <li key={issue} className="text-xs leading-relaxed text-ink-muted">• {issue}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-ink-muted">
                No issues detected: no missing prices, no non-positive prices, no duplicate dates and
                no calendar mismatches.
              </p>
            )}
          </CardBody>
        </Card>
      ) : null}

      {config ? (
        <Card>
          <CardHeader title="Financial assumptions" subtitle="Configurable in the backend environment." />
          <CardBody className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Risk-free rate"
              value={formatPercent(Number(config.riskFreeRate))}
              sub="used by Sharpe and Sortino"
            />
            <Stat label="Trading days / year" value={String(config.tradingDaysPerYear)} sub="annualisation factor" />
            <Stat label="VaR confidence" value={formatPercent(Number(config.varConfidence), 0)} />
            <Stat
              label="Default transaction cost"
              value={`${Number(config.defaultTransactionCostBps).toFixed(0)} bps`}
              sub="assumption, editable per run"
            />
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Connecting a live data provider"
          subtitle="API keys are never sent to the browser."
        />
        <CardBody className="space-y-3 text-sm leading-relaxed text-ink-muted">
          <p>
            The backend reads its configuration from environment variables. Copy{" "}
            <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">.env.example</code> to{" "}
            <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">.env</code> and set:
          </p>
          <pre className="overflow-x-auto rounded-lg border border-line bg-stone-50 p-3 text-xs leading-relaxed text-ink">
{`MARKET_DATA_PROVIDER=real
MARKET_DATA_BASE_URL=https://your-provider.example.com
MARKET_DATA_API_KEY=your_key_here      # server-side only
RISK_FREE_RATE=0.065
DEFAULT_LOOKBACK_YEARS=10`}
          </pre>
          <p>
            The provider must expose <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">/assets</code>,{" "}
            <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">/history</code> and{" "}
            <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">/quote</code> — the contract is
            documented in <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs">docs/DATA_PROVIDERS.md</code>.
            If the provider fails, the API returns a clear error or serves cached data with a
            timestamp; it never substitutes demo data for a configured live provider.
          </p>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => window.open("https://github.com/", "_blank", "noopener,noreferrer")}
          >
            Read the provider contract
          </Button>
        </CardBody>
      </Card>

      <Disclaimer>
        Demo data is synthetic. Switching to a live provider does not change any calculation — every
        page, chart and optimiser reads from the same analytics engine.
      </Disclaimer>
    </div>
  );
}
