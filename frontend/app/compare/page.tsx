"use client";

import { useMemo } from "react";
import Link from "next/link";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { AllocationDonut, toClassSlices } from "@/components/charts/AllocationDonut";
import { LineSeriesChart } from "@/components/charts/LineSeriesChart";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import { useApi } from "@/lib/hooks/useApi";
import { formatPercent, formatScore, riskBandTone } from "@/lib/format";
import { cn } from "@/lib/utils";

const ROWS: { key: string; label: string; format: (value: number) => string; better: "high" | "low" | "none" }[] = [
  { key: "expectedReturn", label: "Expected Return", format: (v) => formatPercent(v), better: "high" },
  { key: "volatility", label: "Volatility", format: (v) => formatPercent(v), better: "low" },
  { key: "sharpe", label: "Sharpe", format: (v) => v.toFixed(2), better: "high" },
  { key: "sortino", label: "Sortino", format: (v) => v.toFixed(2), better: "high" },
  { key: "maxDrawdown", label: "Max Drawdown", format: (v) => formatPercent(v), better: "high" },
  { key: "historicalVaR", label: "VaR (95%)", format: (v) => formatPercent(v), better: "low" },
  { key: "historicalCVaR", label: "CVaR (95%)", format: (v) => formatPercent(v), better: "low" },
  { key: "riskScore", label: "Risk Score", format: (v) => `${Math.round(v)}/100`, better: "low" },
];

export default function ComparePage() {
  const { plans, compare, toggleCompare } = useApp();
  const { classOf, names } = useAssets();
  const selected = plans.filter((plan) => compare.includes(plan.id));

  const { data: growth } = useApi(async () => {
    if (!selected.length) return null;
    const results = await Promise.all(
      selected.map((plan) =>
        api
          .backtest({ weights: plan.metrics.weights, initialValue: 1_000_000, rebalanceFrequency: "quarterly" })
          .then((result) => ({ id: plan.id, name: plan.name, curve: result.portfolio.performanceCurve ?? [], dates: result.portfolio.dates ?? [] }))
          .catch(() => null),
      ),
    );
    return results.filter(Boolean) as { id: string; name: string; curve: number[]; dates: string[] }[];
  }, [compare.join(",")]);

  const value = (plan: (typeof selected)[number], key: string) => {
    if (key === "riskScore") return plan.metrics.riskScore?.score ?? Number.NaN;
    return (plan.metrics as unknown as Record<string, number>)[key] ?? Number.NaN;
  };

  const bestIndex = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of ROWS) {
      if (row.better === "none" || selected.length < 2) continue;
      const values = selected.map((plan) => value(plan, row.key));
      if (values.some((v) => !Number.isFinite(v))) continue;
      map[row.key] = row.better === "high" ? values.indexOf(Math.max(...values)) : values.indexOf(Math.min(...values));
    }
    return map;
  }, [selected]);

  const palette = ["#4338CA", "#0F766E", "#B45309", "#7C3AED", "#0E7490"];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Compare portfolios</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Up to five plans side by side. The best value in each row is highlighted.
          </p>
        </div>
        {selected.length ? (
          <Button variant="secondary" size="sm" onClick={() => selected.forEach((plan) => toggleCompare(plan.id))}>
            Clear selection
          </Button>
        ) : null}
      </header>

      {!selected.length ? (
        <Card>
          <EmptyState
            title="No plans selected"
            description="Open a plan and choose “Compare” to add it here. You can compare up to five at a time."
            action={
              <Link href="/recommendations">
                <Button size="sm">Go to plans</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Side-by-side comparison of selected portfolios</caption>
                <thead className="bg-stone-50 text-left">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-xs font-medium text-ink-muted">Metric</th>
                    {selected.map((plan, index) => (
                      <th key={plan.id} scope="col" className="px-3 py-3 text-right">
                        <span className="flex items-center justify-end gap-2">
                          <span
                            aria-hidden
                            className="h-2 w-2 rounded-full"
                            style={{ background: palette[index % palette.length] }}
                          />
                          <span className="text-xs font-semibold text-ink">{plan.name}</span>
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr key={row.key} className="border-t border-line">
                      <th scope="row" className="px-4 py-2.5 text-left text-xs font-medium text-ink-muted">
                        {row.label}
                      </th>
                      {selected.map((plan, index) => {
                        const isBest = bestIndex[row.key] === index && selected.length > 1;
                        return (
                          <td
                            key={plan.id}
                            className={cn(
                              "num px-3 py-2.5 text-right font-medium",
                              isBest ? "bg-accent-50 text-accent-800" : "text-ink",
                            )}
                          >
                            {row.format(value(plan, row.key))}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="border-t border-line">
                    <th scope="row" className="px-4 py-2.5 text-left text-xs font-medium text-ink-muted">
                      Risk band
                    </th>
                    {selected.map((plan) => (
                      <td key={plan.id} className="px-3 py-2.5 text-right">
                        <span
                          className={cn(
                            "rounded-md border px-2 py-0.5 text-[0.7rem] font-medium",
                            riskBandTone(plan.metrics.riskScore?.band ?? ""),
                          )}
                        >
                          {plan.metrics.riskScore?.band}
                        </span>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {selected.map((plan, index) => (
              <Card key={plan.id}>
                <CardHeader
                  title={plan.name}
                  subtitle={`${formatScore(plan.metrics.riskScore?.score)} risk score`}
                  action={
                    <Button size="sm" variant="ghost" onClick={() => toggleCompare(plan.id)}>
                      Remove
                    </Button>
                  }
                />
                <CardBody>
                  <AllocationDonut
                    data={toClassSlices(plan.metrics.weights, classOf)}
                    height={150}
                    centerLabel="Return"
                    centerValue={formatPercent(plan.metrics.expectedReturn, 1)}
                  />
                  <ul className="mt-3 space-y-1">
                    {Object.entries(plan.metrics.weights)
                      .filter(([, weight]) => weight > 0.005)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 5)
                      .map(([symbol, weight]) => (
                        <li key={symbol} className="flex justify-between gap-3 text-xs">
                          <span className="truncate text-ink-muted">{names[symbol] ?? symbol}</span>
                          <span className="num shrink-0 font-medium text-ink">{formatPercent(weight, 1)}</span>
                        </li>
                      ))}
                  </ul>
                  <div className="mt-3">
                    <Link href={`/portfolio/${plan.id}`}>
                      <Button size="sm" variant="secondary">Full analysis</Button>
                    </Link>
                  </div>
                  <span
                    aria-hidden
                    className="mt-3 block h-1 w-full rounded-full"
                    style={{ background: palette[index % palette.length] }}
                  />
                </CardBody>
              </Card>
            ))}
          </div>

          {growth?.length ? (
            <Card>
              <CardHeader title="Historical growth" subtitle="Time-weighted growth of ₹100 invested in each plan." />
              <CardBody>
                <LineSeriesChart
                  dates={growth[0].dates}
                  height={300}
                  valueFormat="currency-multiple"
                  series={growth.map((series, index) => ({
                    key: series.id,
                    label: series.name,
                    color: palette[index % palette.length],
                    values: series.curve,
                  }))}
                />
              </CardBody>
            </Card>
          ) : null}
        </>
      )}

      <Disclaimer>
        Comparisons use the same historical period and assumptions for every plan. “Best” in a row
        means best on that single historical metric — not best for you overall.
      </Disclaimer>
    </div>
  );
}
