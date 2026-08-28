"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Stat } from "@/components/ui/Stat";
import { ProgressNote, Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { PlanCard } from "@/components/portfolio/PlanCard";
import { AllocationDonut, AllocationLegend, toClassSlices } from "@/components/charts/AllocationDonut";
import { LineSeriesChart } from "@/components/charts/LineSeriesChart";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import { useApi } from "@/lib/hooks/useApi";
import { formatINR, formatPercent, formatScore, riskBandTone } from "@/lib/format";
import type { Asset } from "@/types";

export default function DashboardPage() {
  const { profile, plans, compare, toggleCompare, hydrated, universe } = useApp();
  const { classOf, names } = useAssets();

  const { data: assets } = useApi<Asset[]>(() => api.assets(), []);
  const { data: growth, loading: growthLoading } = useApi(() => {
    const best = plans.find((plan) => plan.bestFit) ?? plans[0];
    if (!best) return Promise.resolve(null);
    return api.backtest({
      weights: best.metrics.weights,
      initialValue: 1_000_000,
      rebalanceFrequency: "quarterly",
    }).catch(() => null);
  }, [plans]);

  const best = plans.find((plan) => plan.bestFit) ?? plans[0] ?? null;
  const slices = best ? toClassSlices(best.metrics.weights, classOf) : [];

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------------ hero */}
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Your portfolio, optimized around your risk.
        </h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          {plans.length
            ? "Plans are generated from your profile against the selected historical data."
            : "Generate plans to populate this dashboard."}
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="card-pad">
            <Stat
              label="Capital"
              value={formatINR(profile.initialInvestment, { compact: true })}
              sub={`+ ${formatINR(profile.monthlyContribution, { compact: true })} / month`}
            />
          </Card>
          <Card className="card-pad">
            <Stat
              label="Risk profile"
              value={profile.riskBand}
              sub={`Score ${Math.round(profile.riskScore)}/100`}
            />
          </Card>
          <Card className="card-pad">
            <Stat label="Horizon" value={`${profile.horizonYears} years`} />
          </Card>
          <Card className="card-pad">
            <Stat
              label="Objective"
              value={profile.objective.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase())}
            />
          </Card>
        </div>
      </section>

      {!hydrated ? (
        <Card><CardBody className="flex items-center gap-2 py-8 text-sm text-ink-muted"><Spinner /> Loading…</CardBody></Card>
      ) : !plans.length ? (
        <Card>
          <CardBody className="py-12 text-center">
            <h2 className="text-base font-semibold text-ink">No plans generated yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
              Complete the five-step profile and the engine will generate and rank candidate
              portfolios for you.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link href="/onboarding"><Button>Build My Investment Plan</Button></Link>
              <Link href="/analytics"><Button variant="secondary">Explore the Analytics</Button></Link>
            </div>
          </CardBody>
        </Card>
      ) : (
        <>
          {/* ------------------------------------------------ recommended */}
          <section>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold tracking-tight text-ink">Recommended plans</h2>
              <div className="flex gap-2">
                {compare.length ? (
                  <Link href="/compare">
                    <Button size="sm" variant="secondary">Compare {compare.length}</Button>
                  </Link>
                ) : null}
                <Link href="/recommendations">
                  <Button size="sm" variant="ghost">View all</Button>
                </Link>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {plans.slice(0, 3).map((plan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  classOf={classOf}
                  comparing={compare.includes(plan.id)}
                  onCompare={toggleCompare}
                />
              ))}
            </div>
          </section>

          {/* -------------------------------------------- portfolio analytics */}
          {best ? (
            <section className="grid gap-4 lg:grid-cols-3">
              <Card className="lg:col-span-1">
                <CardHeader title="Best-fit allocation" subtitle={best.name} />
                <CardBody>
                  <AllocationDonut
                    data={slices}
                    height={190}
                    centerLabel="Expected return"
                    centerValue={formatPercent(best.metrics.expectedReturn, 1)}
                  />
                  <AllocationLegend data={slices} />
                </CardBody>
              </Card>
              <Card className="lg:col-span-2">
                <CardHeader
                  title="Historical growth"
                  subtitle="Time-weighted growth of ₹100, versus Nifty 50, gold and the 10-year government bond."
                />
                <CardBody>
                  {growthLoading || !growth ? (
                    <ProgressNote>Computing backtest…</ProgressNote>
                  ) : (
                    <LineSeriesChart
                      dates={growth.portfolio.dates ?? []}
                      height={260}
                      valueFormat="currency-multiple"
                      series={[
                        {
                          key: "portfolio",
                          label: best.name,
                          color: "#4338CA",
                          values: growth.portfolio.performanceCurve ?? [],
                          area: true,
                        },
                        ...growth.benchmarks.map((benchmark) => ({
                          key: benchmark.symbol,
                          label: benchmark.name,
                          color:
                            benchmark.symbol === "NIFTY50"
                              ? "#A8A29E"
                              : benchmark.symbol === "GOLD"
                                ? "#B45309"
                                : "#0F766E",
                          values: (benchmark.performanceCurve ?? benchmark.equityCurve ?? []).map(
                            (value, index, array) => (array[0] ? value / array[0] : value),
                          ),
                          dashed: true,
                        })),
                      ]}
                    />
                  )}
                </CardBody>
              </Card>
            </section>
          ) : null}
        </>
      )}

      {/* ------------------------------------------------- market overview */}
      <section>
        <h2 className="mb-3 text-lg font-semibold tracking-tight text-ink">Market overview</h2>
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">
                Asset universe with latest price, historical return, volatility and drawdown
              </caption>
              <thead className="bg-stone-50 text-left text-xs text-ink-muted">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Asset</th>
                  <th scope="col" className="px-3 py-2 font-medium">Class</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Price</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Return</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Volatility</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Sharpe</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {(assets ?? [])
                  .filter((asset) => !universe.length || universe.includes(asset.symbol))
                  .slice(0, 12)
                  .map((asset) => (
                    <tr key={asset.symbol} className="border-t border-line">
                      <td className="px-4 py-2">
                        <span className="block font-medium text-ink">{asset.name}</span>
                        <span className="block text-xs text-ink-subtle">{asset.symbol}</span>
                      </td>
                      <td className="px-3 py-2 text-ink-muted">{asset.assetClass.replace(/_/g, " ")}</td>
                      <td className="num px-3 py-2 text-right">{formatINR(asset.price ?? null, { decimals: 2 })}</td>
                      <td className="num px-3 py-2 text-right">{formatPercent(asset.annualizedReturn)}</td>
                      <td className="num px-3 py-2 text-right">{formatPercent(asset.volatility)}</td>
                      <td className="num px-3 py-2 text-right">{asset.sharpe?.toFixed(2) ?? "—"}</td>
                      <td className="num px-3 py-2 text-right text-ink-muted">
                        {formatPercent(asset.maxDrawdown)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-line px-4 py-3">
            <Link href="/assets">
              <Button size="sm" variant="secondary">See full asset universe</Button>
            </Link>
          </div>
        </Card>
      </section>

      <Disclaimer>
        Figures are model estimates computed from historical data over the period shown in the data
        status indicator. Not investment advice and not a prediction of future results.
      </Disclaimer>
    </div>
  );
}
