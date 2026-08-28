"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_STYLE, GRID_COLOR } from "./ChartFrame";
import { formatPercent, formatNumber } from "@/lib/format";

/** Histogram of periodic returns with a VaR reference line. */
export function DistributionChart({
  bins,
  counts,
  varValue,
  height = 260,
}: {
  bins: number[];
  counts: number[];
  varValue?: number | null;
  height?: number;
}) {
  const data = bins.map((bin, index) => ({ bin, count: counts[index] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} vertical={false} />
        <XAxis
          dataKey="bin"
          tick={AXIS_STYLE}
          stroke="#DAD6D2"
          tickFormatter={(value: number) => formatPercent(value, 1)}
          minTickGap={24}
        />
        <YAxis tick={AXIS_STYLE} stroke="#DAD6D2" width={40} />
        <Tooltip
          cursor={{ fill: "#F5F5F4" }}
          contentStyle={{ borderRadius: 8, border: "1px solid #E7E5E4", fontSize: 12 }}
          labelFormatter={(value: number) => `Return ${formatPercent(value, 2)}`}
          formatter={(value: number) => [`${value} periods`, "Frequency"]}
        />
        <Bar dataKey="count" radius={[2, 2, 0, 0]}>
          {data.map((entry) => (
            <Cell
              key={entry.bin}
              fill={entry.bin < 0 ? "#B91C1C" : "#0F766E"}
              fillOpacity={0.75}
            />
          ))}
        </Bar>
        {varValue != null ? (
          <ReferenceLine
            x={-varValue}
            stroke="#B45309"
            strokeDasharray="4 3"
            label={{ value: "VaR", position: "top", style: { fontSize: 10, fill: "#B45309" } }}
          />
        ) : null}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function describeDistribution(bins: number[]) {
  if (!bins.length) return "";
  return `Bins span ${formatPercent(Math.min(...bins), 2)} to ${formatPercent(Math.max(...bins), 2)} per period.`;
}

export { formatNumber };
