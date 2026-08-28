"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { Stat } from "@/components/ui/Stat";
import { ErrorState, ProgressNote, Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { MetricGrid } from "@/components/portfolio/MetricGrid";
import { ExplanationPanel } from "@/components/portfolio/ExplanationPanel";
import { RiskScoreBreakdown } from "@/components/portfolio/RiskScoreBreakdown";
import { AssumptionBar } from "@/components/portfolio/AssumptionBar";
import { AllocationEditor } from "@/components/portfolio/AllocationEditor";
import { AllocationDonut, AllocationLegend, toClassSlices } from "@/components/charts/AllocationDonut";
import { LineSeriesChart } from "@/components/charts/LineSeriesChart";
import { MonteCarloFanChart } from "@/components/charts/MonteCarloFanChart";
import { CorrelationHeatmap } from "@/components/charts/CorrelationHeatmap";
import { BarList } from "@/components/charts/BarList";
import { ChartFrame, downloadCsv } from "@/components/charts/ChartFrame";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import {
  classLabel,
  formatINR,
  formatNumber,
  formatPercent,
  formatScore,
  riskBandTone,
} from "@/lib/format";
import { cn } from "@/lib/utils";

type Tab = "overview" | "whatif" | "risk" | "simulation";

const BENCHMARK_COLORS: Record<string, string> = {
  NIFTY50: "#A8A29E",
  GOLD: "#B45309",
  GSEC10Y: "#0F766E",
};

export default function PortfolioDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { plans, hydrated } = useApp();
  const { classOf, names, loading: assetsLoading } = useAssets();
  const [tab, setTab] = useState<Tab>("overview");

  const plan = plans.find((item) => item.id === params.id) ?? null;

  const [correlation, setCorrelation] = useState<{ symbols: string[]; matrix: (number | null)[][] } | null>(null);
  const [backtest, setBacktest] = useState<Awaited<ReturnType<typeof api.backtest>> | null>(null);
  const [projection, setProjection] = useState<Awaited<ReturnType<typeof api.monteCarlo>> | null>(null);
  const [stress, setStress] = useState<Awaited<ReturnType<typeof api.stressTest>> | null>(null);
  const [whatIf, setWhatIf] = useState<Record<string, number> | null>(null);
  const [whatIfMetrics, setWhatIfMetrics] = useState<Awaited<ReturnType<typeof api.whatIf>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const weights = whatIf ?? plan?.metrics.weights ?? {};
  const heldSymbols = useMemo(
    () => Object.entries(weights).filter(([, weight]) => weight > 1e-6).map(([symbol]) => symbol),
    [weights],
  );

  // Load the analytical panels once the plan is known.
  useEffect(() => {
    if (!plan) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const payload = { weights: plan.metrics.weights, symbols: heldSymbols.length ? heldSymbols : undefined };

    Promise.all([
      api.correlation({ symbols: heldSymbols }),
      api.backtest({
        ...payload,
        initialValue: 1_000_000,
        monthlyContribution: 0,
        rebalanceFrequency: "quarterly",
      }),
      api.stressTest({ ...payload, portfolioValue: 1_000_000 }),
    ])
      .then(([corr, bt, st]) => {
        if (cancelled) return;
        setCorrelation(corr);
        setBacktest(bt);
        setStress(st);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load analytics.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan?.id]);

  // Recompute metrics whenever the user moves a slider.
  useEffect(() => {
    if (!whatIf) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .whatIf({ weights: whatIf })
        .then((result) => {
          if (!cancelled) setWhatIfMetrics(result);
        })
        .catch(() => undefined);
    }, 220);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [whatIf]);

  const classSlices = useMemo(() => toClassSlices(plan?.metrics.weights ?? {}, classOf), [plan, classOf]);
  const whatIfSlices = useMemo(() => toClassSlices(weights, classOf), [weights, classOf]);

  if (!hydrated || assetsLoading) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-ink-muted">
        <Spinner /> Loading portfolio…
      </div>
    );
  }

  if (!plan) {
    return (
      <Card>
        <CardBody className="py-12 text-center">
          <h1 className="text-base font-semibold text-ink">This plan is no longer available</h1>
          <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
            Plans are held in this browser session. Regenerate them from your profile to continue.
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Button onClick={() => router.push("/recommendations?generate=1")}>Regenerate plans</Button>
            <Link href="/onboarding">
              <Button variant="secondary">Edit profile</Button>
            </Link>
          </div>
        </CardBody>
      </Card>
    );
  }

  const metrics = plan.metrics;
  const portfolioSeries = backtest?.portfolio;
  const sliderNames = Object.fromEntries(heldSymbols.map((symbol) => [symbol, names[symbol] ?? symbol]));

  return (
    <div className="space-y-6">
      {/* ---------------------------------------------------------- header */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">{plan.name}</h1>
            <span
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium",
                riskBandTone(metrics.riskScore?.band ?? ""),
              )}
            >
              {metrics.riskScore?.band} risk
            </span>
            {plan.bestFit ? <Badge tone="accent">Best Fit</Badge> : null}
          </div>
          <p className="mt-1.5 text-sm text-ink-muted">
            {plan.summary} · {plan.positions ?? heldSymbols.length} holdings
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/compare">
            <Button variant="secondary" size="sm">Compare plans</Button>
          </Link>
          <Link href="/recommendations">
            <Button variant="ghost" size="sm">All plans</Button>
          </Link>
        </div>
      </header>

      <AssumptionBar assumptions={metrics.assumptions} />

      {/* ------------------------------------------------- headline metrics */}
      <Card>
        <CardBody>
          <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
            <div>
              <p className="label mb-2">Asset allocation</p>
              <AllocationDonut
                data={classSlices}
                height={190}
                centerLabel="Expected return"
                centerValue={formatPercent(metrics.expectedReturn, 1)}
              />
              <AllocationLegend data={classSlices} />
            </div>
            <div>
              <MetricGrid metrics={metrics} />
              <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    const rows = heldSymbols.map((symbol) => [
                      symbol,
                      names[symbol] ?? symbol,
                      classLabel(classOf[symbol] ?? "other"),
                      (weights[symbol] * 100).toFixed(2),
                    ]);
                    downloadCsv(`${plan.id}-allocation.csv`, rows, ["Symbol", "Name", "Asset class", "Weight %"]);
                  }}
                >
                  Download allocation
                </Button>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      <Tabs
        items={[
          { id: "overview", label: "Overview" },
          { id: "whatif", label: "What if?" },
          { id: "risk", label: "Risk & correlation" },
          { id: "simulation", label: "Scenarios & projection" },
        ]}
        value={tab}
        onChange={(value) => setTab(value as Tab)}
      />

      {loading ? <ProgressNote>Computing historical analytics for this allocation…</ProgressNote> : null}
      {error ? <ErrorState message={error} /> : null}

      {/* ------------------------------------------------------- overview */}
      {tab === "overview" ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <CardHeader
                title="Historical growth"
                subtitle="Time-weighted growth of ₹100 invested, versus single-asset benchmarks."
                action={
                  portfolioSeries?.dates ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        const dates = portfolioSeries.dates ?? [];
                        const performance = portfolioSeries.performanceCurve ?? [];
                        const rows = dates.map((date, index) => [
                          date,
                          performance[index]?.toFixed(4) ?? "",
                        ]);
                        downloadCsv(`${plan.id}-growth.csv`, rows, ["Date", "Growth of 1"]);
                      }}
                    >
                      Download
                    </Button>
                  ) : null
                }
              />
              <CardBody>
                {portfolioSeries?.dates?.length ? (
                  <LineSeriesChart
                    dates={portfolioSeries.dates}
                    height={300}
                    valueFormat="currency-multiple"
                    series={[
                      {
                        key: "portfolio",
                        label: plan.name,
                        color: "#4338CA",
                        values: (portfolioSeries.performanceCurve ?? []).map((value) => value),
                        area: true,
                      },
                      ...(backtest?.benchmarks ?? []).map((benchmark) => ({
                        key: benchmark.symbol,
                        label: benchmark.name,
                        color: BENCHMARK_COLORS[benchmark.symbol] ?? "#A8A29E",
                        values: (benchmark.performanceCurve ?? benchmark.equityCurve ?? []).map(
                          (value, index, array) => (array[0] ? value / array[0] : value),
                        ),
                        dashed: true,
                      })),
                    ]}
                  />
                ) : (
                  <p className="py-10 text-center text-sm text-ink-muted">Loading history…</p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Drawdown" subtitle="Decline from the previous peak, measured on the time-weighted curve." />
              <CardBody>
                {portfolioSeries?.dates?.length && portfolioSeries.drawdownSeries?.length ? (
                  <LineSeriesChart
                    dates={portfolioSeries.dates}
                    height={220}
                    valueFormat="percent"
                    series={[
                      {
                        key: "drawdown",
                        label: "Drawdown",
                        color: "#B91C1C",
                        values: portfolioSeries.drawdownSeries,
                        area: true,
                      },
                    ]}
                  />
                ) : (
                  <p className="py-10 text-center text-sm text-ink-muted">Loading drawdowns…</p>
                )}
                {metrics.drawdowns?.length ? (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-sm">
                      <caption className="sr-only">Deepest historical drawdown episodes</caption>
                      <thead className="text-left text-xs text-ink-muted">
                        <tr>
                          <th scope="col" className="py-1 font-medium">Depth</th>
                          <th scope="col" className="py-1 font-medium">Peak</th>
                          <th scope="col" className="py-1 font-medium">Trough</th>
                          <th scope="col" className="py-1 font-medium">Recovered</th>
                          <th scope="col" className="py-1 text-right font-medium">Recovery</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.drawdowns.slice(0, 5).map((episode, index) => (
                          <tr key={index} className="border-t border-line">
                            <td className="num py-1.5 text-negative">{formatPercent(episode.depth)}</td>
                            <td className="py-1.5 text-ink-muted">{episode.peakDate ?? "—"}</td>
                            <td className="py-1.5 text-ink-muted">{episode.troughDate ?? "—"}</td>
                            <td className="py-1.5 text-ink-muted">{episode.recovered ? "Yes" : "Not yet"}</td>
                            <td className="num py-1.5 text-right text-ink-muted">
                              {episode.recoveryPeriods != null ? `${episode.recoveryPeriods} periods` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Where the return and the risk come from" />
              <CardBody className="grid gap-6 sm:grid-cols-2">
                <div>
                  <p className="label mb-3">Share of expected return</p>
                  <BarList
                    items={(metrics.returnContribution ?? []).slice(0, 8).map((row) => ({
                      key: row.symbol,
                      label: names[row.symbol] ?? row.symbol,
                      value: row.share,
                      secondaryValue: row.weight,
                      secondaryLabel: "weight",
                    }))}
                    color="#4338CA"
                  />
                </div>
                <div>
                  <p className="label mb-3">Share of portfolio risk</p>
                  <BarList
                    items={(metrics.riskContribution ?? []).slice(0, 8).map((row) => ({
                      key: row.symbol,
                      label: names[row.symbol] ?? row.symbol,
                      value: row.riskShare,
                      secondaryValue: row.weight,
                      secondaryLabel: "weight",
                    }))}
                    color="#B45309"
                    secondary="Equal capital allocation does not mean equal risk: a holding's risk share reflects both its volatility and its correlation with everything else."
                  />
                </div>
              </CardBody>
            </Card>
          </div>

          <div className="space-y-4">
            <ExplanationPanel explanation={plan.explanation} />
            <Card>
              <CardHeader title="Scoring breakdown" subtitle="How this plan ranked against the candidate pool." />
              <CardBody>
                <ul className="space-y-2">
                  {Object.entries(plan.subScores).map(([key, value]) => (
                    <li key={key} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-ink-muted">
                        {key.replace(/([A-Z])/g, " $1").replace(/^./, (character) => character.toUpperCase())}
                      </span>
                      <span className="num font-medium text-ink">{formatNumber(value, 3)}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 border-t border-line pt-3 text-xs text-ink-subtle">
                  Sub-scores are normalised across the evaluated candidates, so 1.0 is the best in
                  the pool rather than an absolute grade.
                </p>
              </CardBody>
            </Card>
          </div>
        </div>
      ) : null}

      {/* --------------------------------------------------------- what if */}
      {tab === "whatif" ? (
        <div className="space-y-4">
          <AllocationEditor
            weights={weights}
            onChange={(symbol, weight) =>
              setWhatIf((current) => ({ ...(current ?? plan.metrics.weights), [symbol]: weight }))
            }
            onReset={() => {
              setWhatIf(null);
              setWhatIfMetrics(null);
            }}
            metrics={whatIfMetrics?.metrics ?? (whatIf ? null : plan.metrics)}
            loading={Boolean(whatIf) && !whatIfMetrics}
            classOf={classOf}
            names={sliderNames}
          />
          <Disclaimer variant="strong">
            Adjusting weights re-runs the same historical calculations on your new allocation. It
            shows what <em>would have</em> happened over the selected period — not what will happen.
          </Disclaimer>
        </div>
      ) : null}

      {/* ------------------------------------------------------------ risk */}
      {tab === "risk" ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader
              title="Correlation between holdings"
              subtitle="Pearson correlation of daily returns across the selected period. Lower correlation between holdings means more diversification benefit."
            />
            <CardBody>
              {correlation ? (
                <CorrelationHeatmap symbols={correlation.symbols} matrix={correlation.matrix} />
              ) : (
                <p className="py-10 text-center text-sm text-ink-muted">Loading correlation…</p>
              )}
            </CardBody>
          </Card>
          <div className="space-y-4">
            <Card>
              <CardHeader title="Platform Risk Score" />
              <CardBody>
                <RiskScoreBreakdown riskScore={metrics.riskScore} />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Diversification" />
              <CardBody className="space-y-3">
                <Stat
                  label="Effective positions"
                  value={formatNumber(metrics.effectiveAssets, 1)}
                  sub="equally weighted equivalent"
                  hint="1 / Herfindahl index of weights. Eleven holdings skewed to one asset behave like far fewer."
                />
                <Stat
                  label="Diversification ratio"
                  value={formatNumber(metrics.diversificationRatio)}
                  sub="weighted avg vol ÷ portfolio vol"
                  hint="Above 1.0 means combining the assets reduced volatility versus holding them separately."
                />
                <Stat
                  label="Weighted liquidity"
                  value={formatNumber(metrics.weightedLiquidity, 2)}
                  sub="relative tradability, 0–1"
                />
              </CardBody>
            </Card>
          </div>
        </div>
      ) : null}

      {/* ------------------------------------------------------ simulation */}
      {tab === "simulation" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Hypothetical stress scenarios"
              subtitle="Instantaneous shocks applied to each asset class. Assumptions are editable on the Scenarios page."
            />
            <CardBody>
              {stress ? (
                <div className="space-y-3">
                  {stress.scenarios.map((scenario) => (
                    <div key={scenario.key} className="rounded-lg border border-line p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-ink">{scenario.name}</p>
                          <p className="mt-0.5 text-xs text-ink-subtle">{scenario.description}</p>
                        </div>
                        <span
                          className={cn(
                            "num shrink-0 text-sm font-semibold",
                            scenario.portfolioImpact < 0 ? "text-negative" : "text-positive",
                          )}
                        >
                          {formatPercent(scenario.portfolioImpact, 1)}
                        </span>
                      </div>
                      <p className="num mt-1.5 text-xs text-ink-muted">
                        {formatINR(scenario.valueBefore, { compact: true })} →{" "}
                        {formatINR(scenario.valueAfter, { compact: true })}
                      </p>
                    </div>
                  ))}
                  <Disclaimer variant="strong">{stress.scenarios[0]?.caveat}</Disclaimer>
                </div>
              ) : (
                <p className="py-10 text-center text-sm text-ink-muted">Loading scenarios…</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Illustrative projection"
              subtitle="Monte Carlo simulation using the historical mean and covariance of this allocation."
              action={
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => void runProjection()}
                  disabled={Boolean(projection) && false}
                >
                  {projection ? "Recalculate" : "Run 10,000 paths"}
                </Button>
              }
            />
            <CardBody>
              {projection ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <Stat label="P10" value={formatINR(projection.finalValues.p10, { compact: true })} />
                    <Stat label="Median" value={formatINR(projection.finalValues.p50, { compact: true })} />
                    <Stat label="P90" value={formatINR(projection.finalValues.p90, { compact: true })} />
                  </div>
                  <ChartFrame title="Range of outcomes" subtitle="Shaded bands show the 10th–90th percentile range.">
                    <MonteCarloFanChart
                      yearsAxis={projection.yearsAxis}
                      percentilePaths={projection.percentilePaths}
                      height={260}
                    />
                  </ChartFrame>
                  <p className="text-xs text-ink-subtle">
                    Total invested {formatINR(projection.totalInvested, { compact: true })} · probability
                    of ending below that: {formatPercent(projection.probabilityOfLoss, 1)}
                  </p>
                  <Disclaimer variant="strong">
                    Illustrative model scenarios based on historical and statistical assumptions.
                    Not a forecast, not a range of guaranteed outcomes. Costs and taxes are not
                    modelled.
                  </Disclaimer>
                </div>
              ) : (
                <div className="space-y-3 py-6">
                  <p className="text-center text-sm text-ink-muted">
                    Run a projection to see a range of possible outcomes for this allocation.
                  </p>
                  <div className="flex justify-center">
                    <Button size="sm" onClick={() => void runProjection()}>Run simulation</Button>
                  </div>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}

      <Disclaimer>
        {plan.explanation.caveat} Figures labelled “expected” are model estimates derived from the
        historical period shown above.
      </Disclaimer>
    </div>
  );

  async function runProjection() {
    const profileHorizon = 10;
    const result = await api.monteCarlo({
      weights: plan!.metrics.weights,
      symbols: heldSymbols,
      initialValue: 1_000_000,
      monthlyContribution: 0,
      years: profileHorizon,
      paths: 10_000,
      seed: 42,
    });
    setProjection(result);
  }
}


