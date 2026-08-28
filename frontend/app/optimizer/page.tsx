"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Slider } from "@/components/ui/Slider";
import { Select, Field } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, ProgressNote } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { EfficientFrontierChart } from "@/components/charts/EfficientFrontierChart";
import { AllocationDonut, AllocationLegend, toClassSlices } from "@/components/charts/AllocationDonut";
import { MetricGrid } from "@/components/portfolio/MetricGrid";
import { AssumptionBar } from "@/components/portfolio/AssumptionBar";
import { api, ApiRequestError } from "@/lib/api";
import { useAssets } from "@/lib/hooks/useAssets";
import { useApi } from "@/lib/hooks/useApi";
import { formatPercent } from "@/lib/format";
import type { AssetClass } from "@/types";

const STRATEGIES = [
  { id: "min_variance", label: "Minimum Variance", description: "Lowest historical volatility that still satisfies the constraints." },
  { id: "max_sharpe", label: "Maximum Sharpe", description: "Best historical return per unit of volatility." },
  { id: "risk_parity", label: "Risk Parity", description: "Every holding contributes an equal share of portfolio risk." },
  { id: "max_diversification", label: "Maximum Diversification", description: "Maximises the weighted average volatility divided by portfolio volatility." },
  { id: "max_return_for_risk", label: "Max Return under Risk Cap", description: "Highest expected return while staying under a volatility ceiling." },
  { id: "min_cvar", label: "Minimum CVaR", description: "Minimises the average loss on the worst days (expected shortfall)." },
];

const CLASSES: AssetClass[] = [
  "equity", "bond", "gold", "silver", "commodity", "international_equity", "reit", "cash",
];

export default function OptimizerPage() {
  const { classOf, names, assets } = useAssets();
  const [maxWeight, setMaxWeight] = useState(0.4);
  const [maxVolatility, setMaxVolatility] = useState(0.18);
  const [classCaps, setClassCaps] = useState<Record<string, number>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  const [strategy, setStrategy] = useState("max_sharpe");
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.optimize>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);

  const symbols = excluded.length
    ? assets.map((asset) => asset.symbol).filter((symbol) => !excluded.includes(symbol))
    : undefined;

  const { data: frontier } = useApi(
    () =>
      api.frontier({
        symbols,
        maxWeight,
        maxVolatility,
        classBounds: buildClassBounds(classCaps),
        points: 45,
      }),
    [maxWeight, maxVolatility, JSON.stringify(classCaps), excluded.join(",")],
  );

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        symbols,
        strategies: [strategy],
        maxWeight,
        maxVolatility,
        classBounds: buildClassBounds(classCaps),
        targetVolatility: strategy === "max_return_for_risk" ? maxVolatility : undefined,
      };
      setResult(await api.optimize(payload));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err : new ApiRequestError("Optimization failed.", 0));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const outcome = result?.results?.[0];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Portfolio optimizer</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Run any of six strategies under your own constraints and see where the result sits on the
          efficient frontier.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        {/* ---------------------------------------------------- controls */}
        <div className="space-y-4">
          <Card>
            <CardHeader title="Constraints" subtitle="These apply to every strategy and to the frontier." />
            <CardBody className="space-y-5">
              <Slider
                label="Maximum single-asset weight"
                value={Math.round(maxWeight * 100)}
                min={5}
                max={100}
                step={5}
                onChange={(value) => setMaxWeight(value / 100)}
                format={(value) => `${value}%`}
              />
              <Slider
                label="Maximum portfolio volatility"
                value={Math.round(maxVolatility * 1000)}
                min={20}
                max={400}
                step={5}
                onChange={(value) => setMaxVolatility(value / 1000)}
                format={(value) => `${(value / 10).toFixed(1)}%`}
              />

              <div>
                <p className="label mb-2">Asset-class caps (optional)</p>
                <div className="space-y-3">
                  {CLASSES.map((assetClass) => (
                    <Slider
                      key={assetClass}
                      label={assetClass.replace(/_/g, " ")}
                      value={Math.round((classCaps[assetClass] ?? 1) * 100)}
                      min={0}
                      max={100}
                      step={5}
                      onChange={(value) =>
                        setClassCaps((current) => ({ ...current, [assetClass]: value / 100 }))
                      }
                      format={(value) => (value === 100 ? "No cap" : `${value}%`)}
                    />
                  ))}
                </div>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Strategy" />
            <CardBody className="space-y-3">
              <Field label="Optimization strategy">
                <Select value={strategy} onChange={(event) => setStrategy(event.target.value)}>
                  {STRATEGIES.map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </Select>
              </Field>
              <p className="text-xs leading-relaxed text-ink-muted">
                {STRATEGIES.find((item) => item.id === strategy)?.description}
              </p>
              <Button onClick={run} disabled={loading} className="w-full">
                {loading ? "Optimizing…" : "Run optimization"}
              </Button>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Exclusions"
              subtitle="Remove individual instruments from the universe."
            />
            <CardBody>
              <div className="max-h-52 space-y-1.5 overflow-y-auto">
                {assets.map((asset) => (
                  <label key={asset.symbol} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-accent-700"
                      checked={excluded.includes(asset.symbol)}
                      onChange={(event) =>
                        setExcluded((current) =>
                          event.target.checked
                            ? [...current, asset.symbol]
                            : current.filter((symbol) => symbol !== asset.symbol),
                        )
                      }
                    />
                    <span className="truncate text-ink">{asset.name}</span>
                  </label>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>

        {/* ----------------------------------------------------- results */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Efficient frontier"
              subtitle="Hover the curve; the highlighted markers are the minimum-variance and maximum-Sharpe portfolios."
            />
            <CardBody>
              {frontier ? (
                <EfficientFrontierChart
                  points={frontier.points}
                  minVariance={frontier.minVariance}
                  tangency={frontier.tangency}
                  selected={
                    outcome
                      ? { expectedReturn: outcome.metrics.expectedReturn, volatility: outcome.metrics.volatility }
                      : null
                  }
                  height={340}
                />
              ) : (
                <ProgressNote>Computing the frontier for the current constraints…</ProgressNote>
              )}
            </CardBody>
          </Card>

          {loading ? <ProgressNote>Running {STRATEGIES.find((item) => item.id === strategy)?.label}…</ProgressNote> : null}

          {error ? (
            <ErrorState
              title={error.code === "no_feasible_portfolio" ? "No feasible portfolio" : "Optimization failed"}
              message={error.message}
              suggestions={error.suggestions}
            />
          ) : null}

          {outcome ? (
            <>
              <AssumptionBar
                assumptions={result?.assumptions}
                extra={[{ label: "Strategy", value: STRATEGIES.find((item) => item.id === strategy)?.label ?? strategy }]}
              />
              <Card>
                <CardHeader
                  title={STRATEGIES.find((item) => item.id === strategy)?.label ?? strategy}
                  subtitle="Weights solved subject to the constraints on the left."
                  action={<Badge tone="accent">Optimized</Badge>}
                />
                <CardBody className="grid gap-6 lg:grid-cols-[260px_1fr]">
                  <div>
                    <AllocationDonut
                      data={toClassSlices(outcome.metrics.weights, classOf)}
                      height={180}
                      centerLabel="Expected return"
                      centerValue={formatPercent(outcome.metrics.expectedReturn, 1)}
                    />
                    <AllocationLegend data={toClassSlices(outcome.metrics.weights, classOf)} />
                  </div>
                  <div className="space-y-4">
                    <MetricGrid metrics={outcome.metrics} columns={4} />
                    <div>
                      <p className="label mb-2">Holdings</p>
                      <ul className="space-y-1">
                        {Object.entries(outcome.metrics.weights)
                          .filter(([, weight]) => weight > 1e-4)
                          .sort((a, b) => b[1] - a[1])
                          .map(([symbol, weight]) => (
                            <li key={symbol} className="flex justify-between gap-3 text-sm">
                              <span className="truncate text-ink-muted">{names[symbol] ?? symbol}</span>
                              <span className="num shrink-0 font-medium text-ink">
                                {formatPercent(weight, 1)}
                              </span>
                            </li>
                          ))}
                      </ul>
                    </div>
                  </div>
                </CardBody>
              </Card>

              <div className="flex flex-wrap gap-2">
                <Link href="/recommendations">
                  <Button>Generate full plans from this profile</Button>
                </Link>
                <Link href="/backtest">
                  <Button variant="secondary">Backtest this allocation</Button>
                </Link>
              </div>
            </>
          ) : null}
        </div>
      </div>

      <Disclaimer>
        Optimization is performed on historical data. An &ldquo;optimal&rdquo; portfolio is the one
        that scored best on that history under your constraints — it is not expected to be optimal
        going forward.
      </Disclaimer>
    </div>
  );
}

function buildClassBounds(caps: Record<string, number>): Record<string, [number, number]> | undefined {
  const bounds: Record<string, [number, number]> = {};
  for (const [assetClass, cap] of Object.entries(caps)) {
    if (cap < 0.999) bounds[assetClass] = [0, cap];
  }
  return Object.keys(bounds).length ? bounds : undefined;
}
