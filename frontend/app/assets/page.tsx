"use client";

import { useMemo, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import { Tabs } from "@/components/ui/Tabs";
import { TextInput, Select } from "@/components/ui/Field";
import { ErrorState, Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { CorrelationHeatmap } from "@/components/charts/CorrelationHeatmap";
import { ChartFrame, downloadCsv } from "@/components/charts/ChartFrame";
import { LineSeriesChart } from "@/components/charts/LineSeriesChart";
import { DistributionChart } from "@/components/charts/DistributionChart";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks/useApi";
import { formatDate, formatPercent, classLabel } from "@/lib/format";
import type { Asset } from "@/types";

const CLASS_OPTIONS = [
  "all", "equity", "bond", "gold", "silver", "commodity", "international_equity", "reit", "cash",
];

export default function AssetsPage() {
  const { data, error, loading, reload } = useApi(() => api.analytics({}), []);
  const [search, setSearch] = useState("");
  const [assetClass, setAssetClass] = useState("all");
  const [detail, setDetail] = useState<string | null>(null);

  const rows = useMemo(() => (data?.assets ?? []) as Record<string, unknown>[], [data]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter((row) => {
      const symbol = String(row.symbol ?? "").toLowerCase();
      const name = String(row.name ?? "").toLowerCase();
      const matchesQuery = !query || symbol.includes(query) || name.includes(query);
      const matchesClass = assetClass === "all" || row.assetClass === assetClass;
      return matchesQuery && matchesClass;
    });
  }, [rows, search, assetClass]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-ink-muted">
        <Spinner /> Loading asset universe…
      </div>
    );
  }
  if (error || !data) return <ErrorState message={error?.message ?? "No data."} onRetry={reload} />;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Asset universe</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            {rows.length} instruments across equities, fixed income, precious metals, commodities,
            international equity and real assets.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <TextInput
            placeholder="Search name or ticker"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search assets"
            className="w-56"
          />
          <Select value={assetClass} onChange={(event) => setAssetClass(event.target.value)} aria-label="Filter by asset class">
            {CLASS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "All asset classes" : classLabel(option)}
              </option>
            ))}
          </Select>
          <button
            className="h-10 rounded-lg border border-line bg-surface px-3 text-sm text-ink-muted hover:bg-stone-50"
            onClick={() => {
              const header = ["Symbol", "Name", "Class", "Return", "Volatility", "Sharpe", "MaxDD", "Obs"];
              const body = filtered.map((row) => [
                String(row.symbol),
                String(row.name),
                String(row.assetClass),
                Number(row.annualizedReturn),
                Number(row.volatility),
                Number(row.sharpe),
                Number(row.maxDrawdown),
                Number(row.observations),
              ]);
              downloadCsv("asset-universe.csv", body, header);
            }}
          >
            Export CSV
          </button>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="card-pad">
          <Stat label="Instruments" value={String(rows.length)} sub="with usable history" />
        </Card>
        <Card className="card-pad">
          <Stat
            label="Period covered"
            value={`${data.period.start} → ${data.period.end}`}
            sub={`${data.assets.length} series aligned`}
          />
        </Card>
        <Card className="card-pad">
          <Stat
            label="Avg pairwise correlation"
            value={data.correlation.averagePairwiseCorrelation.toFixed(3)}
            sub="across the whole universe"
            hint="Mean of the off-diagonal Pearson correlations. Lower means more diversification is available."
          />
        </Card>
        <Card className="card-pad">
          <Stat
            label="Data quality"
            value={`${data.dataQuality.score}/100`}
            sub={data.dataQuality.grade}
            hint="Composite score from the data-quality pipeline: missing dates, gaps, outliers, calendar mismatches and currency checks."
          />
        </Card>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">
              Asset universe with price, history availability, return, volatility, Sharpe, drawdown and data source
            </caption>
            <thead className="bg-stone-50 text-left text-xs text-ink-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-medium">Asset</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Class</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Sector</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Price</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">History</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Return</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Volatility</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Sharpe</th>
                <th scope="col" className="px-3 py-2.5 text-right font-medium">Max DD</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={String(row.symbol)}
                  className="cursor-pointer border-t border-line hover:bg-stone-50"
                  onClick={() => setDetail(String(row.symbol))}
                >
                  <td className="px-4 py-2.5">
                    <span className="block font-medium text-ink">{String(row.name)}</span>
                    <span className="block text-xs text-ink-subtle">{String(row.symbol)}</span>
                  </td>
                  <td className="px-3 py-2.5 text-ink-muted">{classLabel(String(row.assetClass))}</td>
                  <td className="px-3 py-2.5 text-ink-muted">{String(row.sector)}</td>
                  <td className="num px-3 py-2.5 text-right">
                    ₹{Number(row.price).toFixed(2)}
                    <span className="block text-xs text-ink-subtle">{formatDate(String(row.asOf))}</span>
                  </td>
                  <td className="num px-3 py-2.5 text-right text-ink-muted">
                    {Number(row.observations).toLocaleString("en-IN")}
                    <span className="block text-xs text-ink-subtle">
                      {formatDate(String(row.historyStart))}
                    </span>
                  </td>
                  <td className="num px-3 py-2.5 text-right">{formatPercent(Number(row.annualizedReturn))}</td>
                  <td className="num px-3 py-2.5 text-right">{formatPercent(Number(row.volatility))}</td>
                  <td className="num px-3 py-2.5 text-right">{Number(row.sharpe).toFixed(2)}</td>
                  <td className="num px-3 py-2.5 text-right text-ink-muted">
                    {formatPercent(Number(row.maxDrawdown))}
                  </td>
                  <td className="max-w-[160px] truncate px-3 py-2.5 text-xs text-ink-subtle">
                    {String(row.dataSource)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!filtered.length ? (
          <p className="py-8 text-center text-sm text-ink-muted">No assets match this filter.</p>
        ) : null}
      </Card>

      <Card>
        <CardHeader
          title="Correlation across the universe"
          subtitle="Pearson correlation of daily returns. Negative values indicate assets that have historically moved against each other."
        />
        <CardBody>
          <CorrelationHeatmap symbols={data.correlation.symbols} matrix={data.correlation.matrix} />
        </CardBody>
      </Card>

      {detail ? (
        <Card>
          <CardHeader
            title={`${detail} detail`}
            subtitle="Rolling behaviour and distribution. Close this panel to return to the table."
            action={
              <button className="text-sm text-ink-muted hover:text-ink" onClick={() => setDetail(null)}>
                Close
              </button>
            }
          />
          <CardBody>
            <AssetDetail symbol={detail} />
          </CardBody>
        </Card>
      ) : null}

      <Disclaimer>
        Statistics are computed from the data period shown above. Synthetic demo data is clearly
        labelled in the header&apos;s data status indicator and is not real market data.
      </Disclaimer>
    </div>
  );
}

function AssetDetail({ symbol }: { symbol: string }) {
  const { data, loading } = useApi(async () => {
    const analytics = await api.analytics({ symbols: [symbol] });
    return analytics.assets[0] as Record<string, unknown> | undefined;
  }, [symbol]);

  if (loading || !data) return <p className="py-6 text-center text-sm text-ink-muted">Loading…</p>;

  const descriptive = (data.descriptive ?? {}) as Record<string, number>;
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <dl className="grid grid-cols-2 gap-4">
        <Stat label="Annualised return" value={formatPercent(Number(data.annualizedReturn))} />
        <Stat label="Volatility" value={formatPercent(Number(data.volatility))} />
        <Stat label="Sharpe" value={Number(data.sharpe).toFixed(2)} />
        <Stat label="Sortino" value={Number(data.sortino).toFixed(2)} />
        <Stat label="Max drawdown" value={formatPercent(Number(data.maxDrawdown))} />
        <Stat label="Calmar" value={Number(data.calmar).toFixed(2)} />
        <Stat label="Skewness" value={descriptive.skewness?.toFixed(2) ?? "—"} />
        <Stat label="Excess kurtosis" value={descriptive.kurtosis?.toFixed(2) ?? "—"} />
        <Stat label="Historical VaR" value={formatPercent(Number(data.historicalVaR))} />
        <Stat label="Historical CVaR" value={formatPercent(Number(data.historicalCVaR))} />
      </dl>
      <ChartFrame title="Return distribution" subtitle="Histogram of daily returns" height={220}>
        <DistributionFor symbol={symbol} />
      </ChartFrame>
    </div>
  );
}

function DistributionFor({ symbol }: { symbol: string }) {
  const { data } = useApi(async () => {
    const advanced = await api.advanced({ weights: { [symbol]: 1 }, symbols: [symbol] });
    return advanced.distribution as { bins: number[]; counts: number[] } | undefined;
  }, [symbol]);

  if (!data) return <p className="py-6 text-center text-sm text-ink-muted">Loading…</p>;
  return <DistributionChart bins={data.bins} counts={data.counts} height={220} />;
}
