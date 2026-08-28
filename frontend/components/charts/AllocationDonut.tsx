"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ASSET_CLASS_COLORS, classLabel, formatPercent } from "@/lib/format";

export interface AllocationSlice {
  key: string;
  label: string;
  value: number;
  color?: string;
}

/** Group weights by asset class for the headline allocation chart. */
export function AllocationDonut({
  data,
  height = 200,
  centerLabel,
  centerValue,
}: {
  data: AllocationSlice[];
  height?: number;
  centerLabel?: string;
  centerValue?: string;
}) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0) || 1;
  return (
    <div className="relative w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius="62%"
            outerRadius="92%"
            paddingAngle={1.5}
            stroke="none"
          >
            {data.map((slice) => (
              <Cell
                key={slice.key}
                fill={slice.color ?? ASSET_CLASS_COLORS[slice.key] ?? "#A8A29E"}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              border: "1px solid #E7E5E4",
              fontSize: 12,
              boxShadow: "0 4px 12px -2px rgb(28 25 23 / 0.08)",
            }}
            formatter={(value: number, name: string) => [
              `${formatPercent(value / total, 1)}`,
              name,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[0.65rem] uppercase tracking-wide text-ink-subtle">
          {centerLabel ?? "Allocation"}
        </span>
        <span className="num text-lg font-semibold text-ink">{centerValue ?? ""}</span>
      </div>
    </div>
  );
}

export function AllocationLegend({ data }: { data: AllocationSlice[] }) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0) || 1;
  return (
    <ul className="mt-3 space-y-1.5">
      {data.map((slice) => (
        <li key={slice.key} className="flex items-center justify-between gap-3 text-sm">
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: slice.color ?? ASSET_CLASS_COLORS[slice.key] ?? "#A8A29E" }}
            />
            <span className="truncate text-ink">{slice.label}</span>
          </span>
          <span className="num shrink-0 font-medium text-ink">
            {formatPercent(slice.value / total, 1)}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function toClassSlices(
  weights: Record<string, number>,
  classOf: Record<string, string>,
): AllocationSlice[] {
  const totals = new Map<string, number>();
  for (const [symbol, weight] of Object.entries(weights)) {
    const key = classOf[symbol] ?? "other";
    totals.set(key, (totals.get(key) ?? 0) + weight);
  }
  return [...totals.entries()]
    .map(([key, value]) => ({ key, label: classLabel(key), value }))
    .sort((a, b) => b.value - a.value);
}
