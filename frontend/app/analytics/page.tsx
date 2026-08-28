"use client";

import { useMemo, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Tabs } from "@/components/ui/Tabs";
import { Select } from "@/components/ui/Field";
import { ErrorState, ProgressNote, Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { CorrelationHeatmap } from "@/components/charts/CorrelationHeatmap";
import { LineSeriesChart } from "@/components/charts/LineSeriesChart";
import { DistributionChart } from "@/components/charts/DistributionChart";
import { EfficientFrontierChart } from "@/components/charts/EfficientFrontierChart";
import { BarList } from "@/components/charts/BarList";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks/useApi";
import { formatNumber, formatPercent } from "@/lib/format";

const WINDOWS = [
  { id: "30", label: "30-day", value: 30 },
  { id: "90", label: "90-day", value: 90 },
  { id: "252", label: "1-year", value: 252 },
  { id: "756", label: "3-year", value: 756 },
  { id: "1260", label: "5-year", value: 1260 },
  { id: "full", label: "Full history", value: 0 },
];

type Tab = "performance" | "risk" | "correlation" | "distribution" | "drawdown" | "rolling" | "frontier";

export default function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>("performance");
  const [benchmark, setBenchmark] = useState("NIFTY50");

  const { data, error, loading, reload } = useApi(() => api.analytics({}), []);
  const [windowId, setWindowId] = useState("full");
  const windowValue = WINDOWS.find((item) => item.id === windowId)?.value ?? 0;

  const symbols = useMemo(() => (data?.symbols ?? []).slice(0, 14), [data]);

  const { data: correlation } = useApi(
    () => api.correlation({ symbols, window: windowValue || undefined }),
    [symbols.join(","), windowId],
  );

  const { data: advanced, loading: advancedLoading } = useApi(
    () =>
      api.advanced({
        weights: Object.fromEntries(symbols.map((symbol) => [symbol, 1 / symbols.length])),
        symbols,
        benchmark,
      }),
    [symbols.join(","), benchmark],
  );

  const { data: frontier } = useApi(() => api.frontier({ symbols, points: 40 }), [symbols.join(",")]);

  const { data: growth } = useApi(
    () =>
      api.backtest({
        weights: Object.fromEntries(symbols.map((symbol) => [symbol, 1 / symbols.length])),
        symbols,
        initialValue: 1_000_000,
        rebalanceFrequency: "quarterly",
      }),
    [symbols.join(",")],
  );

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-ink-muted">
        <Spinner /> Loading analytics…
      </div>
    );
  }
  if (error || !data) return <ErrorState message={error?.message ?? "No data."} onRetry={reload} />;

  const rows = data.assets as Record<string, unknown>[];
  const top = (key: string, count = 10, ascending = false) =>
    [...rows]
      .sort((a, b) => (ascending ? Number(a[key]) - Number(b[key]) : Number(b[key]) - Number(a[key])))
      .slice(0, count);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Analytics workspace</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Asset-level statistics across {data.period.start} → {data.period.end}. Data quality{" "}
            {data.dataQuality.score}/100 ({data.dataQuality.grade}).
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={benchmark} onChange={(event) => setBenchmark(event.target.value)} aria-label="Benchmark">
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>{symbol}</option>
            ))}
          </Select>
          <Select value={windowId} onChange={(event) => setWindowId(event.target.value)} aria-label="Window">
            {WINDOWS.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </Select>
        </div>
      </header>

      <Tabs
        items={[
          { id: "performance", label: "Asset performance" },
          { id: "risk", label: "Risk" },
          { id: "correlation", label: "Correlation" },
          { id: "distribution", label: "Distribution" },
          { id: "drawdown", label: "Drawdown" },
          { id: "rolling", label: "Rolling metrics" },
          { id: "frontier", label: "Efficient frontier" },
        ]}
        value={tab}
        onChange={(value) => setTab(value as Tab)}
      />

      {tab === "performance" ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Per-asset performance statistics</caption>
              <thead className="bg-stone-50 text-left text-xs text-ink-muted">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Asset</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Return</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">CAGR</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Volatility</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Sharpe</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Sortino</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Calmar</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Max DD</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Best day</th>
                  <th scope="col" className="px-3 py-2.5 text-right font-medium">Worst day</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={String(row.symbol)} className="border-t border-line">
                    <td className="px-4 py-2.5 font-medium text-ink">{String(row.name)}</td>
                    <td className="num px-3 py-2.5 text-right">{formatPercent(Number(row.annualizedReturn))}</td>
                    <td className="num px-3 py-2.5 text-right">{formatPercent(Number(row.cagr))}</td>
                    <td className="num px-3 py-2.5 text-right">{formatPercent(Number(row.volatility))}</td>
                    <td className="num px-3 py-2.5 text-right">{formatNumber(Number(row.sharpe))}</td>
                    <td className="num px-3 py-2.5 text-right">{formatNumber(Number(row.sortino))}</td>
                    <td className="num px-3 py-2.5 text-right">{formatNumber(Number(row.calmar))}</td>
                    <td className="num px-3 py-2.5 text-right text-ink-muted">{formatPercent(Number(row.maxDrawdown))}</td>
                    <td className="num px-3 py-2.5 text-right text-positive">{formatPercent(Number(row.bestPeriod))}</td>
                    <td className="num px-3 py-2.5 text-right text-negative">{formatPercent(Number(row.worstPeriod))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {tab === "risk" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Highest volatility" subtitle="Annualised standard deviation of daily returns" />
            <CardBody>
              <BarList
                items={top("volatility").map((row) => ({
                  key: String(row.symbol),
                  label: String(row.name),
                  value: Number(row.volatility),
                }))}
                color="#B45309"
              />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Deepest drawdown" subtitle="Worst peak-to-trough decline over the period" />
            <CardBody>
              <BarList
                items={top("maxDrawdown", 10, true).map((row) => ({
                  key: String(row.symbol),
                  label: String(row.name),
                  value: Math.abs(Number(row.maxDrawdown)),
                }))}
                color="#B91C1C"
              />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Downside deviation" subtitle="Volatility of returns below the minimum acceptable return" />
            <CardBody>
              <BarList
                items={top("downsideDeviation").map((row) => ({
                  key: String(row.symbol),
                  label: String(row.name),
                  value: Number(row.downsideDeviation),
                }))}
                color="#7C3AED"
              />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Tail risk" subtitle="Historical 95% CVaR (average loss on the worst 5% of days)" />
            <CardBody>
              <BarList
                items={top("historicalCVaR").map((row) => ({
                  key: String(row.symbol),
                  label: String(row.name),
                  value: Number(row.historicalCVaR),
                }))}
                color="#0E7490"
              />
            </CardBody>
          </Card>
        </div>
      ) : null}

      {tab === "correlation" ? (
        <Card>
          <CardHeader
            title="Correlation matrix"
            subtitle={
              windowValue
                ? `Rolling window of the last ${windowValue} trading days.`
                : "Full history."
            }
          />
          <CardBody>
            {correlation ? (
              <CorrelationHeatmap symbols={correlation.symbols} matrix={correlation.matrix} />
            ) : (
              <p className="py-8 text-center text-sm text-ink-muted">Loading…</p>
            )}
            {correlation ? (
              <p className="mt-3 text-xs text-ink-subtle">
                Average pairwise correlation: {formatNumber(correlation.averagePairwiseCorrelation, 3)}.
                Lower average correlation means the universe offers more diversification.
              </p>
            ) : null}
          </CardBody>
        </Card>
      ) : null}

      {tab === "distribution" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Return distribution"
              subtitle={`Equally weighted basket of ${symbols.length} assets, daily returns`}
            />
            <CardBody>
              {advanced?.distribution ? (
                <DistributionChart
                  bins={(advanced.distribution as { bins: number[] }).bins}
                  counts={(advanced.distribution as { counts: number[] }).counts}
                  height={260}
                />
              ) : (
                <p className="py-8 text-center text-sm text-ink-muted">Loading…</p>
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Distribution statistics" subtitle="Higher moments of the basket's daily returns" />
            <CardBody>
              {advanced?.distribution ? (
                <dl className="grid grid-cols-2 gap-4">
                  {Object.entries(
                    (advanced.distribution as { statistics?: Record<string, number> }).statistics ?? {},
                  ).map(([key, value]) => (
                    <div key={key}>
                      <dt className="label">{key.replace(/([A-Z])/g, " $1")}</dt>
                      <dd className="num mt-0.5 font-semibold text-ink">
                        {typeof value === "number" ? formatNumber(value, 4) : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="py-8 text-center text-sm text-ink-muted">Loading…</p>
              )}
              <p className="mt-4 text-xs leading-relaxed text-ink-subtle">
                Negative skew and high excess kurtosis mean large moves — especially losses — are
                more common than a normal distribution would predict. That is why historical VaR and
                CVaR are reported alongside volatility.
              </p>
            </CardBody>
          </Card>
        </div>
      ) : null}

      {tab === "drawdown" ? (
        <Card>
          <CardHeader
            title="Portfolio drawdown"
            subtitle={`Equally weighted basket of ${symbols.length} assets, rebalanced quarterly`}
          />
          <CardBody>
            {growth ? (
              <LineSeriesChart
                dates={growth.portfolio.dates ?? []}
                height={300}
                valueFormat="percent"
                series={[
                  {
                    key: "dd",
                    label: "Drawdown",
                    color: "#B91C1C",
                    values: growth.portfolio.drawdownSeries ?? [],
                    area: true,
                  },
                ]}
              />
            ) : (
              <ProgressNote>Computing drawdown series…</ProgressNote>
            )}
            {growth?.portfolio ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-4">
                <MiniStat label="Max drawdown" value={formatPercent(growth.portfolio.maxDrawdown)} />
                <MiniStat
                  label="Recovery"
                  value={
                    growth.portfolio.recoveryPeriods != null
                      ? `${growth.portfolio.recoveryPeriods} periods`
                      : "Not recovered"
                  }
                />
                <MiniStat
                  label="Best year"
                  value={growth.portfolio.bestYear ? formatPercent(growth.portfolio.bestYear.return, 1) : "—"}
                />
                <MiniStat label="Win rate" value={formatPercent(growth.portfolio.winRate ?? 0, 1)} />
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : null}

      {tab === "rolling" ? (
        <div className="space-y-4">
          <Card>
            <CardHeader title="Rolling volatility" subtitle="63-day window, annualised" />
            <CardBody>
              {advanced?.rollingVolatility ? (
                <LineSeriesChart
                  dates={(advanced.rollingVolatility as { date: string }[]).map((point) => point.date)}
                  height={240}
                  valueFormat="percent"
                  showLegend={false}
                  series={[
                    {
                      key: "vol",
                      label: "Volatility",
                      color: "#B45309",
                      values: (advanced.rollingVolatility as { value: number }[]).map((point) => point.value),
                    },
                  ]}
                />
              ) : (
                <p className="py-8 text-center text-sm text-ink-muted">Loading…</p>
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Rolling 1-year return" subtitle="252-day window, annualised" />
            <CardBody>
              {advanced?.rollingReturn ? (
                <LineSeriesChart
                  dates={(advanced.rollingReturn as { date: string }[]).map((point) => point.date)}
                  height={240}
                  valueFormat="percent"
                  showLegend={false}
                  series={[
                    {
                      key: "return",
                      label: "Return",
                      color: "#4338CA",
                      values: (advanced.rollingReturn as { value: number }[]).map((point) => point.value),
                    },
                  ]}
                />
              ) : (
                <p className="py-8 text-center text-sm text-ink-muted">Loading…</p>
              )}
            </CardBody>
          </Card>
          {advanced?.betaAlpha ? (
            <Card>
              <CardHeader title={`Versus ${benchmark}`} subtitle="CAPM beta and Jensen's alpha, plus capture ratios" />
              <CardBody className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
                <MiniStat label="Beta" value={formatNumber((advanced.betaAlpha as Record<string, number>).beta)} />
                <MiniStat label="Alpha (ann.)" value={formatPercent((advanced.betaAlpha as Record<string, number>).alpha)} />
                <MiniStat label="R²" value={formatNumber((advanced.betaAlpha as Record<string, number>).rSquared)} />
                <MiniStat label="Tracking error" value={formatPercent(Number(advanced.trackingError))} />
                <MiniStat label="Information ratio" value={formatNumber(Number(advanced.informationRatio))} />
                <MiniStat
                  label="Upside capture"
                  value={formatNumber((advanced.captureRatios as Record<string, number>)?.upsideCapture)}
                />
                <MiniStat
                  label="Downside capture"
                  value={formatNumber((advanced.captureRatios as Record<string, number>)?.downsideCapture)}
                />
              </CardBody>
            </Card>
          ) : null}
          {advancedLoading ? <ProgressNote>Computing rolling metrics…</ProgressNote> : null}
        </div>
      ) : null}

      {tab === "frontier" ? (
        <Card>
          <CardHeader
            title="Efficient frontier"
            subtitle="Minimum achievable volatility for each target return, over the selected universe."
          />
          <CardBody>
            {frontier ? (
              <EfficientFrontierChart
                points={frontier.points}
                minVariance={frontier.minVariance}
                tangency={frontier.tangency}
                height={360}
              />
            ) : (
              <ProgressNote>Computing the frontier…</ProgressNote>
            )}
            {frontier ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                <MiniStat
                  label="Minimum variance"
                  value={`${formatPercent(frontier.minVariance.volatility)} vol · ${formatPercent(frontier.minVariance.expectedReturn)} ret`}
                />
                <MiniStat
                  label="Maximum Sharpe"
                  value={
                    frontier.tangency
                      ? `${formatPercent(frontier.tangency.volatility)} vol · ${formatPercent(frontier.tangency.expectedReturn)} ret`
                      : "—"
                  }
                />
                <MiniStat label="Risk-free rate" value={formatPercent(frontier.riskFreeRate)} />
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : null}

      <Disclaimer>
        All statistics are computed from the data period shown above and describe past behaviour
        only. Rolling windows are shown for the trailing period selected in the header.
      </Disclaimer>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label truncate">{label}</p>
      <p className="num mt-0.5 font-semibold text-ink">{value}</p>
    </div>
  );
}
