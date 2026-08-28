"use client";

import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Stat } from "@/components/ui/Stat";
import { Field, Select, TextInput } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, ProgressNote } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { MonteCarloFanChart } from "@/components/charts/MonteCarloFanChart";
import { ChartFrame } from "@/components/charts/ChartFrame";
import { api, ApiRequestError } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import { formatINR, formatPercent } from "@/lib/format";

const PATHS = [1_000, 5_000, 10_000, 50_000];

export default function MonteCarloPage() {
  const { profile, plans } = useApp();
  const { names } = useAssets();
  const plan = plans.find((item) => item.bestFit) ?? plans[0] ?? null;
  const weights = plan?.metrics.weights ?? {};
  const symbols = Object.keys(weights);

  const [initial, setInitial] = useState(profile.initialInvestment || 1_000_000);
  const [monthly, setMonthly] = useState(profile.monthlyContribution || 20_000);
  const [stepUp, setStepUp] = useState(Math.round((profile.annualContributionIncrease ?? 0) * 100));
  const [years, setYears] = useState(profile.horizonYears || 10);
  const [paths, setPaths] = useState(10_000);
  const [method, setMethod] = useState("normal");
  const [seed, setSeed] = useState(42);
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.monteCarlo>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setResult(
        await api.monteCarlo({
          weights,
          symbols,
          initialValue: initial,
          monthlyContribution: monthly,
          annualContributionIncrease: stepUp / 100,
          years,
          paths,
          method,
          seed,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiRequestError ? err : new ApiRequestError("Simulation failed.", 0));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Monte Carlo simulation</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Project a distribution of outcomes using the historical mean and covariance of your
          allocation. Illustrative model scenarios — not a forecast.
        </p>
      </header>

      <Card>
        <CardHeader title="Simulation settings" />
        <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Initial investment">
            <TextInput value={initial} onChange={(event) => setInitial(Number(event.target.value) || 0)} />
          </Field>
          <Field label="Monthly contribution">
            <TextInput value={monthly} onChange={(event) => setMonthly(Number(event.target.value) || 0)} />
          </Field>
          <Field label="Annual step-up (%)" hint="Increase contributions each year">
            <TextInput value={stepUp} onChange={(event) => setStepUp(Number(event.target.value) || 0)} />
          </Field>
          <Field label="Horizon (years)">
            <TextInput value={years} onChange={(event) => setYears(Number(event.target.value) || 1)} />
          </Field>
          <Field label="Simulations">
            <Select value={String(paths)} onChange={(event) => setPaths(Number(event.target.value))}>
              {PATHS.map((value) => (
                <option key={value} value={value}>{value.toLocaleString("en-IN")}</option>
              ))}
            </Select>
          </Field>
          <Field label="Method" hint="Bootstrap resamples realised history">
            <Select value={method} onChange={(event) => setMethod(event.target.value)}>
              <option value="normal">Normal (parametric)</option>
              <option value="student_t">Student-t (fat tails)</option>
              <option value="bootstrap">Historical bootstrap</option>
            </Select>
          </Field>
          <Field label="Seed" hint="Same seed reproduces the same paths">
            <TextInput value={seed} onChange={(event) => setSeed(Number(event.target.value) || 0)} />
          </Field>
          <div className="flex items-end">
            <Button className="w-full" onClick={run} disabled={loading || !symbols.length}>
              {loading ? "Simulating…" : "Run simulation"}
            </Button>
          </div>
        </CardBody>
        {plan ? (
          <div className="border-t border-line px-4 py-3 text-xs text-ink-subtle sm:px-6">
            Simulating: {plan.name} · expected return{" "}
            {formatPercent(plan.metrics.expectedReturn)} · volatility{" "}
            {formatPercent(plan.metrics.volatility)}
          </div>
        ) : (
          <div className="border-t border-line px-4 py-3 text-xs text-caution sm:px-6">
            No plan found — generate plans first.
          </div>
        )}
      </Card>

      {loading ? <ProgressNote>Running {paths.toLocaleString("en-IN")} simulations…</ProgressNote> : null}
      {error ? <ErrorState message={error.message} suggestions={error.suggestions} /> : null}

      {result ? (
        <>
          <Card>
            <CardBody className="grid gap-5 sm:grid-cols-3 lg:grid-cols-5">
              <Stat label="P10" value={formatINR(result.finalValues.p10, { compact: true })} sub="1 in 10 below" />
              <Stat label="P25" value={formatINR(result.finalValues.p25, { compact: true })} />
              <Stat label="Median (P50)" value={formatINR(result.finalValues.p50, { compact: true })} />
              <Stat label="P75" value={formatINR(result.finalValues.p75, { compact: true })} />
              <Stat label="P90" value={formatINR(result.finalValues.p90, { compact: true })} sub="1 in 10 above" />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Range of outcomes"
              subtitle={`${result.paths.toLocaleString("en-IN")} paths over ${result.years} years · ${result.method}`}
              action={<Badge tone="caution">Illustrative</Badge>}
            />
            <CardBody>
              <ChartFrame height={340}>
                <MonteCarloFanChart
                  yearsAxis={result.yearsAxis}
                  percentilePaths={result.percentilePaths}
                  height={340}
                />
              </ChartFrame>
              <div className="mt-4 grid gap-4 border-t border-line pt-4 sm:grid-cols-4">
                <Stat
                  label="Total invested"
                  value={formatINR(result.totalInvested, { compact: true })}
                  sub={`${formatINR(result.initialValue, { compact: true })} + contributions`}
                />
                <Stat
                  label="Probability of shortfall"
                  value={formatPercent(result.probabilityOfLoss, 1)}
                  sub="ends below amount invested"
                />
                <Stat
                  label="Probability of doubling"
                  value={formatPercent(result.probabilityOfDouble, 1)}
                />
                <Stat
                  label="Model inputs"
                  value={`${formatPercent(result.assumptions.expectedAnnualReturn)} ret`}
                  sub={`${formatPercent(result.assumptions.annualVolatility)} vol`}
                />
              </div>
            </CardBody>
          </Card>

          <Disclaimer variant="strong">
            Illustrative model scenarios based on historical and statistical assumptions. These are
            not guaranteed outcomes, and not a forecast. Costs, taxes and changing correlations are
            not modelled. The same seed always reproduces the same paths.
          </Disclaimer>
        </>
      ) : null}
    </div>
  );
}
