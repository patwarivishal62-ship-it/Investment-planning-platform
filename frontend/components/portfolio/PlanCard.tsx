"use client";

import Link from "next/link";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AllocationDonut } from "@/components/charts/AllocationDonut";
import { formatINR, formatNumber, formatPercent, formatScore, riskBandTone } from "@/lib/format";
import type { Plan } from "@/types";
import { cn } from "@/lib/utils";

/** Plan summary card used on the recommendations grid (spec section 57). */
export function PlanCard({
  plan,
  classOf,
  onCompare,
  comparing,
  onSetBest,
}: {
  plan: Plan;
  classOf: Record<string, string>;
  onCompare?: (planId: string) => void;
  comparing?: boolean;
  onSetBest?: (planId: string) => void;
}) {
  const metrics = plan.metrics;
  const slices = toSlices(metrics.weights, classOf);

  return (
    <Card className={cn("flex h-full flex-col", plan.bestFit && "border-accent-300 ring-1 ring-accent-200")}>
      <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold tracking-tight text-ink">{plan.name}</h3>
            {plan.bestFit ? <Badge tone="accent">Best Fit</Badge> : null}
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span
              className={cn(
                "rounded-md border px-2 py-0.5 text-[0.7rem] font-medium",
                riskBandTone(metrics.riskScore?.band ?? ""),
              )}
            >
              {metrics.riskScore?.band ?? "—"} risk
            </span>
            <span className="num text-xs text-ink-muted">
              Score {formatScore(metrics.riskScore?.score)}
            </span>
          </div>
        </div>
        <div className="shrink-0">
          <AllocationDonut data={slices} height={72} centerValue={`${Math.round(metrics.expectedReturn * 1000) / 10}%`} centerLabel="exp. return" />
        </div>
      </div>

      <CardBody className="flex-1 space-y-4">
        <p className="text-xs leading-relaxed text-ink-muted">{plan.summary}</p>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
          <Row label="Expected return" value={formatPercent(metrics.expectedReturn)} />
          <Row label="Volatility" value={formatPercent(metrics.volatility)} />
          <Row label="Sharpe" value={formatNumber(metrics.sharpe)} />
          <Row label="Sortino" value={formatNumber(metrics.sortino)} />
          <Row label="Max drawdown" value={formatPercent(metrics.maxDrawdown)} />
          <Row label="Risk score" value={formatScore(metrics.riskScore?.score)} />
        </dl>

        <div>
          <p className="label mb-1.5">Top holdings</p>
          <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-stone-100">
            {slices.slice(0, 6).map((slice) => (
              <span
                key={slice.key}
                style={{ width: `${slice.value * 100}%`, background: slice.color }}
              />
            ))}
          </div>
          <p className="mt-1.5 text-[0.7rem] text-ink-subtle">
            {slices.slice(0, 4).map((slice) => `${slice.label} ${formatPercent(slice.value, 0)}`).join(" · ")}
          </p>
        </div>
      </CardBody>

      <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-3">
        <Link href={`/portfolio/${plan.id}`}>
          <Button size="sm">View full analysis</Button>
        </Link>
        {onCompare ? (
          <Button size="sm" variant={comparing ? "secondary" : "ghost"} onClick={() => onCompare(plan.id)}>
            {comparing ? "✓ Comparing" : "Compare"}
          </Button>
        ) : null}
        {onSetBest && !plan.bestFit ? (
          <Button size="sm" variant="ghost" onClick={() => onSetBest(plan.id)}>
            Mark best fit
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-[0.7rem] uppercase tracking-wide text-ink-subtle">{label}</dt>
      <dd className="num truncate font-medium text-ink">{value}</dd>
    </div>
  );
}

function toSlices(weights: Record<string, number>, classOf: Record<string, string>) {
  const totals = new Map<string, number>();
  for (const [symbol, weight] of Object.entries(weights)) {
    const key = classOf[symbol] ?? "other";
    totals.set(key, (totals.get(key) ?? 0) + weight);
  }
  const colors: Record<string, string> = {
    equity: "#4338CA",
    international_equity: "#0E7490",
    bond: "#0F766E",
    gold: "#B45309",
    silver: "#64748B",
    commodity: "#7C3AED",
    reit: "#BE185D",
    cash: "#94A3B8",
    other: "#A8A29E",
  };
  const labels: Record<string, string> = {
    equity: "Equity",
    international_equity: "International",
    bond: "Fixed income",
    gold: "Gold",
    silver: "Silver",
    commodity: "Commodity",
    reit: "REIT / InvIT",
    cash: "Cash",
    other: "Other",
  };
  return [...totals.entries()]
    .map(([key, value]) => ({ key, label: labels[key] ?? key, value, color: colors[key] ?? "#A8A29E" }))
    .sort((a, b) => b.value - a.value);
}

export { formatINR };
