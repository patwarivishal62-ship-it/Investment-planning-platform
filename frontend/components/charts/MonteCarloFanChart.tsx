"use client";

import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_STYLE, GRID_COLOR } from "./ChartFrame";
import { formatINR } from "@/lib/format";

/**
 * Monte Carlo fan chart. Bands are stacked from P10 to P90 so the shaded area
 * widens with uncertainty -- the visual point is that outcomes are a range.
 */
export function MonteCarloFanChart({
  yearsAxis,
  percentilePaths,
  height = 320,
}: {
  yearsAxis: number[];
  percentilePaths: Record<string, number[]>;
  height?: number;
}) {
  const p10 = percentilePaths.p10 ?? [];
  const p25 = percentilePaths.p25 ?? [];
  const p50 = percentilePaths.p50 ?? [];
  const p75 = percentilePaths.p75 ?? [];
  const p90 = percentilePaths.p90 ?? [];

  const data = yearsAxis.map((year, i) => ({
    year,
    p10: p10[i] ?? null,
    band25: p25[i] != null && p10[i] != null ? p25[i] - p10[i] : null,
    band50: p50[i] != null && p25[i] != null ? p50[i] - p25[i] : null,
    band75: p75[i] != null && p50[i] != null ? p75[i] - p50[i] : null,
    band90: p90[i] != null && p75[i] != null ? p90[i] - p75[i] : null,
    median: p50[i] ?? null,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} stackOffset="silhouette">
        <CartesianGrid stroke={GRID_COLOR} vertical={false} />
        <XAxis
          dataKey="year"
          tick={AXIS_STYLE}
          stroke="#DAD6D2"
          tickFormatter={(value: number) => `${value}y`}
          label={{ value: "Years from today", position: "insideBottom", offset: -10, style: { fontSize: 11, fill: "#8F8781" } }}
        />
        <YAxis
          tick={AXIS_STYLE}
          stroke="#DAD6D2"
          width={68}
          tickFormatter={(value: number) => formatINR(value, { compact: true })}
        />
        <Tooltip
          contentStyle={{ borderRadius: 8, border: "1px solid #E7E5E4", fontSize: 12 }}
          labelFormatter={(label: number) => `Year ${label}`}
          formatter={(value: number, name: string) => [formatINR(value), name]}
        />
        <Legend verticalAlign="top" height={26} wrapperStyle={{ fontSize: 12, color: "#6B6560" }} />
        <Area
          type="monotone"
          dataKey="band90"
          name="P75–P90"
          stackId="fan"
          stroke="none"
          fill="#C7D2FE"
          fillOpacity={0.55}
          connectNulls
        />
        <Area
          type="monotone"
          dataKey="band75"
          name="P50–P75"
          stackId="fan"
          stroke="none"
          fill="#C7D2FE"
          fillOpacity={0.75}
          connectNulls
        />
        <Area
          type="monotone"
          dataKey="band50"
          name="P25–P50"
          stackId="fan"
          stroke="none"
          fill="#A5B4FC"
          fillOpacity={0.75}
          connectNulls
        />
        <Area
          type="monotone"
          dataKey="band25"
          name="P10–P25"
          stackId="fan"
          stroke="none"
          fill="#C7D2FE"
          fillOpacity={0.55}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="median"
          name="Median"
          stroke="#4338CA"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
