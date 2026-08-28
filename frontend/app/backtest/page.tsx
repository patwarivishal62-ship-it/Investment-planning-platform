"use client";

import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Stat } from "@/components/ui/Stat";
import { Tabs } from "@/components/ui/Tabs";
import { Field, Select, TextInput } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, ProgressNote } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { LineSeriesChart } from "@/components/charts/LineSeriesChart";
import { api, ApiRequestError } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import { formatINR, formatNumber, formatPercent } from "@/lib/format";

const FREQUENCIES = [
  { id: "none", label: "Buy & hold" },
  { id: "monthly", label: "Monthly" },
  { id: "quarterly", label: "Quarterly" },
  { id: "semiannual", label: "Semi-annual" },
  { id: "annual", label: "Annual" },
  { id: "threshold", label: "Threshold-based" },
];

type Tab = "run" | "rebalance" | "walkforward";

export default function BacktestPage() {
  const { profile, plans } = useApp();
  const { names } = useAssets();
  const [tab, setTab] = useState<Tab>("run");

  const plan = plans.find((item) => item.bestFit) ?? plans[0] ?? null;
  const [weights, setWeights] = useState<Record<string, number> | null>(null);
  const effective = weights ?? plan?.metrics.weights ?? {};
  const symbols = Object.keys(effective);

  const [initial, setInitial] = useState(1_000_000);
  const [monthly, setMonthly] = useState(20_000);
  const [frequency, setFrequency] = useState("quarterly");
  const [cost, setCost] = useState(10);
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.backtest>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);

  const [rebalance, setRebalance] = useState<Awaited<ReturnType<typeof api.rebalance>> | null>(null);
  const [trainEnd, setTrainEnd] = useState("2023-12-31");
  const [walk, setWalk] = useState<Awaited<ReturnType<typeof api.walkForward>> | null>(null);

  async function runBacktest() {
    setLoading(true);
    setError(null);
    try {
      setResult(
        await api.backtest({
          weights: effective,
          symbols,
          initialValue: initial,
          monthlyContribution: monthly,
          rebalanceFrequency: frequency,
          transactionCostBps: cost,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiRequestError ? err : new ApiRequestError("Backtest failed.", 0));
    } finally {
      setLoading(false);
    }
  }

  async function runRebalance() {
    setLoading(true);
    try {
      setRebalance(
        await api.rebalance({
          weights: effective,
          symbols,
          initialValue: initial,
          monthlyContribution: monthly,
          transactionCostBps: cost,
        }),
      );
    } finally {
      setLoading(false);
    }
  }

  async function runWalkForward() {
    setLoading(true);
    setError(null);
    try {
      setWalk(
        await api.walkForward({
          symbols: symbols.length ? symbols : undefined,
          trainEnd,
          strategy: "max_sharpe",
          initialValue: initial,
          monthlyContribution: monthly,
          rebalanceFrequency: frequency,
          transactionCostBps: cost,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiRequestError ? err : new ApiRequestError("Walk-forward failed.", 0));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Backtesting</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Replay an allocation through history with realistic rebalancing, contributions and
          transaction costs — and validate it out of sample.
        </p>
      </header>

      <Tabs
        items={[
          { id: "run", label: "Backtest" },
          { id: "rebalance", label: "Rebalancing study" },
          { id: "walkforward", label: "Walk-forward (out-of-sample)" },
        ]}
        value={tab}
        onChange={(value) => setTab(value as Tab)}
      />

      <Card>
        <CardHeader
          title="Assumptions"
          subtitle="Costs and contributions are assumptions, clearly separated from investment performance."
        />
        <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Initial investment">
            <TextInput value={initial} onChange={(event) => setInitial(Number(event.target.value) || 0)} />
          </Field>
          <Field label="Monthly contribution">
            <TextInput value={monthly} onChange={(event) => setMonthly(Number(event.target.value) || 0)} />
          </Field>
          <Field label="Rebalancing">
            <Select value={frequency} onChange={(event) => setFrequency(event.target.value)}>
              {FREQUENCIES.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </Select>
          </Field>
          <Field label="Transaction cost (bps)" hint="One-way cost on traded notional">
            <TextInput value={cost} onChange={(event) => setCost(Number(event.target.value) || 0)} />
          </Field>
          <div className="flex items-end">
            <Button
              className="w-full"
              onClick={() => (tab === "rebalance" ? runRebalance() : tab === "walkforward" ? runWalkForward() : runBacktest())}
              disabled={loading || !symbols.length}
            >
              {loading ? "Running…" : "Run"}
            </Button>
          </div>
        </CardBody>
        {plan ? (
          <div className="border-t border-line px-4 py-3 text-xs text-ink-subtle sm:px-6">
            Allocation under test: {plan.name} ({symbols.length} holdings)
            {weights ? " · modified" : ""}
            {weights ? (
              <button className="ml-2 text-accent-700 underline" onClick={() => setWeights(null)}>
                reset
              </button>
            ) : null}
          </div>
        ) : (
          <div className="border-t border-line px-4 py-3 text-xs text-caution sm:px-6">
            No plan found. Generate plans first, or pick an allocation on the Optimizer page.
          </div>
        )}
      </Card>

      {loading ? <ProgressNote>Running the simulation…</ProgressNote> : null}
      {error ? <ErrorState message={error.message} suggestions={error.suggestions} /> : null}

      {tab === "run" && result ? (
        <>
          <Card>
            <CardBody className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <Stat
                label="Time-weighted CAGR"
                value={formatPercent(result.portfolio.cagr)}
                sub="investment performance"
                hint="Compounds the periodic returns only. Contributions never inflate it."
              />
              <Stat
                label="Money-weighted return"
                value={formatPercent(result.portfolio.moneyWeightedReturn)}
                sub="IRR of your cash flows"
                hint="Annualised internal rate of return including the timing of every contribution."
              />
              <Stat
                label="Ending value"
                value={formatINR(result.portfolio.endValue, { compact: true })}
                sub={`invested ${formatINR(result.portfolio.invested, { compact: true })}`}
              />
              <Stat
                label="Max drawdown"
                value={formatPercent(result.portfolio.maxDrawdown)}
                sub="time-weighted"
                tone={result.portfolio.maxDrawdown < -0.25 ? "negative" : "default"}
              />
              <Stat label="Volatility" value={formatPercent(result.portfolio.volatility)} />
              <Stat label="Sharpe" value={formatNumber(result.portfolio.sharpe)} />
              <Stat label="Sortino" value={formatNumber(result.portfolio.sortino)} />
              <Stat
                label="Transaction costs"
                value={formatINR(result.portfolio.totalCosts ?? 0, { compact: true })}
                sub={`${result.portfolio.rebalanceEvents ?? 0} rebalances`}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Growth of the account"
              subtitle="Account value including contributions, versus the time-weighted performance curve."
            />
            <CardBody>
              <LineSeriesChart
                dates={result.portfolio.dates ?? []}
                height={320}
                valueFormat="currency-multiple"
                series={[
                  {
                    key: "account",
                    label: "Account value",
                    color: "#4338CA",
                    values: (result.portfolio.equityCurve ?? []).map(
                      (value, index, array) => (array[0] ? value / array[0] : value),
                    ),
                    area: true,
                  },
                  {
                    key: "twr",
                    label: "Investment performance (no cash flows)",
                    color: "#0F766E",
                    values: result.portfolio.performanceCurve ?? [],
                    dashed: true,
                  },
                  ...result.benchmarks.map((benchmark) => ({
                    key: benchmark.symbol,
                    label: benchmark.name,
                    color: benchmark.symbol === "NIFTY50" ? "#A8A29E" : benchmark.symbol === "GOLD" ? "#B45309" : "#0E7490",
                    values: (benchmark.performanceCurve ?? benchmark.equityCurve ?? []).map(
                      (value, index, array) => (array[0] ? value / array[0] : value),
                    ),
                    dashed: true,
                  })),
                ]}
              />
            </CardBody>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Calendar-year returns" />
              <CardBody>
                <div className="space-y-1.5">
                  {(result.portfolio.calendarYears ?? []).map((year) => (
                    <div key={year.year} className="flex items-center gap-3">
                      <span className="num w-12 shrink-0 text-xs text-ink-muted">{year.year}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-stone-100">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(Math.abs(year.return) * 200, 100)}%`,
                            background: year.return >= 0 ? "#0F766E" : "#B91C1C",
                          }}
                        />
                      </div>
                      <span className="num w-16 shrink-0 text-right text-xs font-medium text-ink">
                        {formatPercent(year.return, 1)}
                      </span>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Benchmark comparison" subtitle="Same contributions, same period" />
              <CardBody>
                <table className="w-full text-sm">
                  <caption className="sr-only">Portfolio versus benchmark statistics</caption>
                  <thead className="text-left text-xs text-ink-muted">
                    <tr>
                      <th scope="col" className="py-1 font-medium">Asset</th>
                      <th scope="col" className="py-1 text-right font-medium">CAGR</th>
                      <th scope="col" className="py-1 text-right font-medium">Volatility</th>
                      <th scope="col" className="py-1 text-right font-medium">Max DD</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-t border-line">
                      <td className="py-1.5 font-medium text-ink">{plan?.name ?? "Portfolio"}</td>
                      <td className="num py-1.5 text-right">{formatPercent(result.portfolio.cagr)}</td>
                      <td className="num py-1.5 text-right">{formatPercent(result.portfolio.volatility)}</td>
                      <td className="num py-1.5 text-right">{formatPercent(result.portfolio.maxDrawdown)}</td>
                    </tr>
                    {result.benchmarks.map((benchmark) => (
                      <tr key={benchmark.symbol} className="border-t border-line">
                        <td className="py-1.5 text-ink-muted">{benchmark.name}</td>
                        <td className="num py-1.5 text-right">{formatPercent(benchmark.cagr)}</td>
                        <td className="num py-1.5 text-right">{formatPercent(benchmark.volatility)}</td>
                        <td className="num py-1.5 text-right">{formatPercent(benchmark.maxDrawdown)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-3 text-xs text-ink-subtle">
                  Winning periods {result.portfolio.winningPeriods.toLocaleString("en-IN")} · losing
                  periods {result.portfolio.losingPeriods.toLocaleString("en-IN")} · win rate{" "}
                  {formatPercent(result.portfolio.winRate ?? 0, 1)}
                </p>
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}

      {tab === "rebalance" ? (
        <Card>
          <CardHeader
            title="Buy & hold versus periodic rebalancing"
            subtitle="Same allocation, same period — only the rebalancing rule changes."
          />
          <CardBody>
            {rebalance ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">Comparison of rebalancing frequencies</caption>
                  <thead className="bg-stone-50 text-left text-xs text-ink-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-medium">Rule</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">CAGR</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Volatility</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Max DD</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Turnover</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Costs</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Ending value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rebalance.results.map((row) => (
                      <tr key={row.frequency} className="border-t border-line">
                        <td className="px-3 py-2 font-medium text-ink">
                          {row.label}
                          {String(row.frequency) === frequency ? (
                            <Badge tone="accent" className="ml-2">current</Badge>
                          ) : null}
                        </td>
                        <td className="num px-3 py-2 text-right">{formatPercent(row.cagr)}</td>
                        <td className="num px-3 py-2 text-right">{formatPercent(row.volatility)}</td>
                        <td className="num px-3 py-2 text-right">{formatPercent(row.maxDrawdown)}</td>
                        <td className="num px-3 py-2 text-right">{formatNumber(row.totalTurnover ?? 0, 2)}</td>
                        <td className="num px-3 py-2 text-right">{formatINR(row.totalCosts ?? 0, { compact: true })}</td>
                        <td className="num px-3 py-2 text-right">{formatINR(row.endValue, { compact: true })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyHint onRun={runRebalance} />
            )}
          </CardBody>
        </Card>
      ) : null}

      {tab === "walkforward" ? (
        <>
          <Card>
            <CardBody>
              <Field label="Training window ends" hint="The optimiser only ever sees data up to this date.">
                <TextInput value={trainEnd} onChange={(event) => setTrainEnd(event.target.value)} />
              </Field>
            </CardBody>
          </Card>
          {walk ? (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader title="In-sample" subtitle={`${String(walk.assumptions.trainStart ?? "")} → ${String(walk.assumptions.trainEnd ?? "")}`} />
                  <CardBody className="grid grid-cols-2 gap-4">
                    <Stat label="CAGR" value={formatPercent(walk.inSample.cagr)} />
                    <Stat label="Volatility" value={formatPercent(walk.inSample.volatility)} />
                    <Stat label="Sharpe" value={formatNumber(walk.inSample.sharpe)} />
                    <Stat label="Max drawdown" value={formatPercent(walk.inSample.maxDrawdown)} />
                  </CardBody>
                </Card>
                <Card>
                  <CardHeader
                    title="Out-of-sample"
                    subtitle={`${String(walk.assumptions.testStart ?? "")} → ${String(walk.assumptions.testEnd ?? "")}`}
                    action={<Badge tone="positive">Unseen by the optimiser</Badge>}
                  />
                  <CardBody className="grid grid-cols-2 gap-4">
                    <Stat label="CAGR" value={formatPercent(walk.outOfSample.cagr)} />
                    <Stat label="Volatility" value={formatPercent(walk.outOfSample.volatility)} />
                    <Stat label="Sharpe" value={formatNumber(walk.outOfSample.sharpe)} />
                    <Stat label="Max drawdown" value={formatPercent(walk.outOfSample.maxDrawdown)} />
                  </CardBody>
                </Card>
              </div>
              <Card>
                <CardHeader
                  title="Out-of-sample equity curves"
                  subtitle="The portfolio weights were frozen at the end of the training window."
                />
                <CardBody>
                  <LineSeriesChart
                    dates={walk.outOfSample.dates ?? []}
                    height={300}
                    valueFormat="currency-multiple"
                    series={[
                      {
                        key: "oos",
                        label: "Optimised portfolio",
                        color: "#4338CA",
                        values: walk.outOfSample.performanceCurve ?? [],
                        area: true,
                      },
                      ...(walk.benchmarkOutOfSample
                        ? []
                        : []),
                    ]}
                  />
                </CardBody>
              </Card>
              <Disclaimer variant="strong">
                Out-of-sample results are genuinely out of sample: weights were fitted only on data
                before {String(walk.assumptions.trainEnd ?? "")} and then applied to the later period without
                refitting. A large gap between in-sample and out-of-sample performance is a warning
                that the historical fit may not persist.
              </Disclaimer>
            </>
          ) : (
            <Card>
              <CardBody>
                <EmptyHint onRun={runWalkForward} />
              </CardBody>
            </Card>
          )}
        </>
      ) : null}

      <Disclaimer>
        Backtests are computed on historical data with the cost assumptions you set. They exclude
        taxes and slippage, and past results do not indicate future performance.
      </Disclaimer>
    </div>
  );
}

function EmptyHint({ onRun }: { onRun: () => void }) {
  return (
    <div className="py-8 text-center">
      <p className="text-sm text-ink-muted">Run the analysis to populate this table.</p>
      <Button className="mt-4" size="sm" onClick={onRun}>Run</Button>
    </div>
  );
}
