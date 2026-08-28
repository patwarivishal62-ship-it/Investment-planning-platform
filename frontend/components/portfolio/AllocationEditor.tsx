"use client";

import { useMemo } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Slider } from "@/components/ui/Slider";
import { AllocationDonut, AllocationLegend } from "@/components/charts/AllocationDonut";
import { MetricGrid } from "./MetricGrid";
import { ASSET_CLASS_COLORS, classLabel, formatPercent } from "@/lib/format";
import type { PortfolioMetrics } from "@/types";

/**
 * "What if?" simulator (spec section 31). Moving a slider immediately
 * recomputes every risk and return metric through the backend.
 */
export function AllocationEditor({
  weights,
  onChange,
  onReset,
  metrics,
  loading,
  classOf,
  names = {},
}: {
  weights: Record<string, number>;
  onChange: (symbol: string, weight: number) => void;
  onReset: () => void;
  metrics: PortfolioMetrics | null;
  loading: boolean;
  classOf: Record<string, string>;
  names?: Record<string, string>;
}) {
  const entries = useMemo(
    () =>
      Object.entries(weights)
        .filter(([, weight]) => weight > 1e-6)
        .sort((a, b) => b[1] - a[1]),
    [weights],
  );

  const total = entries.reduce((sum, [, weight]) => sum + weight, 0);

  const slices = useMemo(() => {
    const totals = new Map<string, number>();
    for (const [symbol, weight] of Object.entries(weights)) {
      const key = classOf[symbol] ?? "other";
      totals.set(key, (totals.get(key) ?? 0) + weight);
    }
    return [...totals.entries()]
      .map(([key, value]) => ({ key, label: classLabel(key), value }))
      .sort((a, b) => b.value - a.value);
  }, [weights, classOf]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader
          title="Adjust the allocation"
          subtitle="Drag any holding. Every metric on the right recalculates from the same historical data."
          action={
            <Button size="sm" variant="secondary" onClick={onReset}>
              Reset
            </Button>
          }
        />
        <CardBody className="space-y-4">
          {entries.map(([symbol, weight]) => (
            <Slider
              key={symbol}
              label={`${names[symbol] ?? symbol}`}
              value={Math.round(weight * 1000)}
              min={0}
              max={1000}
              step={5}
              onChange={(value) => onChange(symbol, value / 1000)}
              format={(value) => `${(value / 10).toFixed(1)}%`}
              hint={classLabel(classOf[symbol] ?? "other")}
            />
          ))}
          <div className="flex items-center justify-between border-t border-line pt-3 text-sm">
            <span className="text-ink-muted">Total</span>
            <span
              className={
                Math.abs(total - 1) > 0.005 ? "num font-semibold text-caution" : "num font-semibold text-ink"
              }
            >
              {formatPercent(total, 1)}
            </span>
          </div>
          <p className="text-xs text-ink-subtle">
            Weights are renormalised to 100% server-side before any calculation, so the metrics
            always describe a fully invested portfolio.
          </p>
        </CardBody>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader title="Result" subtitle={loading ? "Recalculating…" : "Updated live"} />
          <CardBody>
            <AllocationDonut data={slices} height={180} centerLabel="Positions" centerValue={String(entries.length)} />
            <AllocationLegend data={slices} />
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            {metrics ? (
              <MetricGrid metrics={metrics} columns={3} compact />
            ) : (
              <p className="py-6 text-center text-sm text-ink-muted">
                {loading ? "Recalculating…" : "No metrics yet."}
              </p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export { ASSET_CLASS_COLORS };
