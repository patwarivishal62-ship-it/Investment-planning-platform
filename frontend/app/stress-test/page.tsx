"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Stat } from "@/components/ui/Stat";
import { Slider } from "@/components/ui/Slider";
import { Field, TextInput } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, ProgressNote } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { BarList } from "@/components/charts/BarList";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import { classLabel, formatINR, formatPercent } from "@/lib/format";

interface ShockRow {
  id: string;
  scope: "assetClass" | "symbol";
  target: string;
  shock: number;
}

const TEMPLATE_SHOCKS: Record<string, ShockRow[]> = {
  equity_crash: [
    { id: "1", scope: "assetClass", target: "equity", shock: -0.30 },
    { id: "2", scope: "assetClass", target: "international_equity", shock: -0.25 },
    { id: "3", scope: "assetClass", target: "commodity", shock: -0.15 },
    { id: "4", scope: "assetClass", target: "gold", shock: 0.05 },
    { id: "5", scope: "assetClass", target: "bond", shock: 0.02 },
  ],
  inflation_shock: [
    { id: "1", scope: "assetClass", target: "commodity", shock: 0.20 },
    { id: "2", scope: "assetClass", target: "gold", shock: 0.12 },
    { id: "3", scope: "assetClass", target: "bond", shock: -0.08 },
    { id: "4", scope: "assetClass", target: "equity", shock: -0.10 },
  ],
  rate_shock: [
    { id: "1", scope: "assetClass", target: "bond", shock: -0.12 },
    { id: "2", scope: "assetClass", target: "reit", shock: -0.18 },
    { id: "3", scope: "assetClass", target: "equity", shock: -0.08 },
    { id: "4", scope: "assetClass", target: "gold", shock: -0.05 },
  ],
  recession: [
    { id: "1", scope: "assetClass", target: "equity", shock: -0.22 },
    { id: "2", scope: "assetClass", target: "commodity", shock: -0.18 },
    { id: "3", scope: "assetClass", target: "reit", shock: -0.25 },
    { id: "4", scope: "assetClass", target: "bond", shock: 0.06 },
    { id: "5", scope: "assetClass", target: "gold", shock: 0.08 },
  ],
};

const CLASSES = ["equity", "international_equity", "bond", "gold", "silver", "commodity", "reit", "cash"];

export default function StressTestPage() {
  const { plans } = useApp();
  const { classOf, names } = useAssets();
  const plan = plans.find((item) => item.bestFit) ?? plans[0] ?? null;
  const weights = plan?.metrics.weights ?? {};
  const symbols = Object.keys(weights);

  const [portfolioValue, setPortfolioValue] = useState(1_000_000);
  const [rows, setRows] = useState<ShockRow[]>(TEMPLATE_SHOCKS.equity_crash);
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.stressTest>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exposure = useMemo(() => {
    const totals = new Map<string, number>();
    for (const [symbol, weight] of Object.entries(weights)) {
      const key = classOf[symbol] ?? "other";
      totals.set(key, (totals.get(key) ?? 0) + weight);
    }
    return totals;
  }, [weights, classOf]);

  async function run(custom = false) {
    setLoading(true);
    setError(null);
    try {
      const payload = custom
        ? {
            weights,
            symbols,
            portfolioValue,
            scenarios: ["custom"],
            customShocks: rows.map((row) => ({ scope: row.scope, target: row.target, shock: row.shock })),
          }
        : { weights, symbols, portfolioValue };
      setResult(await api.stressTest(payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress test failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (symbols.length && !result) void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbols.length]);

  const custom = result?.scenarios.find((scenario) => scenario.key === "custom");

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Scenario analysis</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Apply hypothetical shocks to each asset class and see the portfolio impact. Assumptions are
          fully editable — nothing here is a forecast.
        </p>
      </header>

      <Card>
        <CardBody className="flex flex-wrap items-end gap-4">
          <Field label="Portfolio value" className="w-48">
            <TextInput value={portfolioValue} onChange={(event) => setPortfolioValue(Number(event.target.value) || 0)} />
          </Field>
          <div className="text-sm text-ink-muted">
            {plan ? (
              <>Testing: <span className="font-medium text-ink">{plan.name}</span> · {symbols.length} holdings</>
            ) : (
              <span className="text-caution">Generate a plan first to run scenarios.</span>
            )}
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Your current exposure" subtitle="Share of the portfolio by asset class" />
          <CardBody>
            <BarList
              items={[...exposure.entries()]
                .map(([key, value]) => ({ key, label: classLabel(key), value }))
                .sort((a, b) => b.value - a.value)}
              color="#4338CA"
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Hypothetical scenarios"
            subtitle="Pre-defined templates. Each applies an instantaneous shock by asset class."
            action={<Badge tone="caution">Illustrative</Badge>}
          />
          <CardBody className="space-y-3">
            {loading ? <ProgressNote>Applying shocks…</ProgressNote> : null}
            {error ? <ErrorState message={error} /> : null}
            {result?.scenarios
              .filter((scenario) => scenario.key !== "custom")
              .map((scenario) => (
                <div key={scenario.key} className="rounded-lg border border-line p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-ink">{scenario.name}</p>
                      <p className="mt-0.5 text-xs text-ink-subtle">{scenario.description}</p>
                    </div>
                    <span
                      className={
                        scenario.portfolioImpact < 0
                          ? "num shrink-0 text-sm font-semibold text-negative"
                          : "num shrink-0 text-sm font-semibold text-positive"
                      }
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
            <Disclaimer variant="strong">
              {result?.scenarios[0]?.caveat ??
                "Hypothetical instantaneous shocks based on the assumptions shown; not a forecast."}
            </Disclaimer>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Build your own scenario"
          subtitle="Set a shock for any asset class, then apply it to the portfolio."
          action={<Button size="sm" onClick={() => run(true)} disabled={loading}>Apply custom scenario</Button>}
        />
        <CardBody className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            {CLASSES.map((assetClass) => {
              const row = rows.find((item) => item.target === assetClass);
              const value = row?.shock ?? 0;
              return (
                <Slider
                  key={assetClass}
                  label={`${classLabel(assetClass)}${exposure.get(assetClass) ? ` (${formatPercent(exposure.get(assetClass)!, 0)} held)` : ""}`}
                  value={Math.round(value * 200)}
                  min={-100}
                  max={100}
                  step={1}
                  onChange={(next) => {
                    const shock = next / 200;
                    setRows((current) => {
                      const existing = current.find((item) => item.target === assetClass);
                      if (existing) {
                        return current.map((item) =>
                          item.target === assetClass ? { ...item, shock } : item,
                        );
                      }
                      return [
                        ...current,
                        { id: String(Date.now()), scope: "assetClass", target: assetClass, shock },
                      ];
                    });
                  }}
                  format={(next) => `${(next / 2).toFixed(1)}%`}
                />
              );
            })}
          </div>

          {custom ? (
            <div className="rounded-lg border border-accent-200 bg-accent-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-accent-900">Custom scenario impact</p>
                  <p className="num mt-0.5 text-xs text-accent-800">
                    {formatINR(custom.valueBefore)} → {formatINR(custom.valueAfter)}
                  </p>
                </div>
                <div className="text-right">
                  <Stat
                    label="Portfolio impact"
                    value={formatPercent(custom.portfolioImpact, 2)}
                    tone={custom.portfolioImpact < 0 ? "negative" : "positive"}
                  />
                </div>
              </div>
              <ul className="mt-3 space-y-1">
                {custom.assets
                  .filter((asset) => asset.contribution !== 0)
                  .slice(0, 8)
                  .map((asset) => (
                    <li key={asset.symbol} className="flex justify-between gap-3 text-xs text-accent-900">
                      <span className="truncate">{names[asset.symbol] ?? asset.symbol}</span>
                      <span className="num shrink-0">
                        {formatPercent(asset.shock, 0)} × {formatPercent(asset.weight, 0)} ={" "}
                        {formatPercent(asset.contribution, 2)}
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {Object.entries(TEMPLATE_SHOCKS).map(([key, template]) => (
              <Button
                key={key}
                size="sm"
                variant="secondary"
                onClick={() => setRows(template.map((row) => ({ ...row })))}
              >
                Load {key.replace(/_/g, " ")}
              </Button>
            ))}
            <Button size="sm" variant="ghost" onClick={() => setRows([])}>
              Clear all
            </Button>
          </div>
        </CardBody>
      </Card>

      {result?.historicalWindows?.length ? (
        <Card>
          <CardHeader
            title="Worst realised windows"
            subtitle="Observed history rather than assumptions: the deepest rolling losses this allocation actually experienced."
            action={<Badge tone="positive">Observed</Badge>}
          />
          <CardBody>
            <ul className="space-y-2">
              {result.historicalWindows.map((window) => (
                <li key={window.label} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-ink-muted">{window.label}</span>
                  <span className="num shrink-0 font-medium text-negative">
                    {formatPercent(window.return, 2)}
                  </span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
