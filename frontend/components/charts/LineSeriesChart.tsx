"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AXIS_STYLE, GRID_COLOR } from "./ChartFrame";
import { formatNumber, formatPercent } from "@/lib/format";
import { DataProvenanceTag } from "./ChartFrame";

export interface Series {
  key: string;
  label: string;
  color: string;
  values: (number | null)[];
  dashed?: boolean;
  area?: boolean;
}

/** Multi-series time-series chart used for growth, drawdowns and rolling metrics. */
export function LineSeriesChart({
  dates,
  series,
  height = 300,
  valueFormat = "number",
  yFormat,
  showLegend = true,
  zeroLine = false,
}: {
  dates: string[];
  series: Series[];
  height?: number;
  valueFormat?: "number" | "percent" | "currency-multiple";
  yFormat?: (value: number) => string;
  showLegend?: boolean;
  zeroLine?: boolean;
}) {
  const data = dates.map((date, index) => {
    const row: Record<string, string | number | null> = { date };
    for (const s of series) row[s.key] = s.values[index] ?? null;
    return row;
  });

  const formatValue = (value: number) => {
    if (yFormat) return yFormat(value);
    if (valueFormat === "percent") return formatPercent(value, 0);
    if (valueFormat === "currency-multiple") return `${formatNumber(value, 2)}×`;
    return formatNumber(value, 2);
  };

  const tickFormatter = (value: string) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
  };

  return (
    <div className="w-full">

    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} vertical={false} />
        <XAxis
          dataKey="date"
          tick={AXIS_STYLE}
          tickFormatter={tickFormatter}
          minTickGap={48}
          stroke="#DAD6D2"
        />
        <YAxis
          tick={AXIS_STYLE}
          tickFormatter={(value: number) => formatValue(value)}
          stroke="#DAD6D2"
          width={58}
        />
        {zeroLine ? (
          <CartesianGrid stroke="#D6D3D1" strokeDasharray="3 3" vertical={false} y={0} />
        ) : null}
        <Tooltip
          contentStyle={{
            borderRadius: 8,
            border: "1px solid #E7E5E4",
            fontSize: 12,
            boxShadow: "0 4px 12px -2px rgb(28 25 23 / 0.08)",
          }}
          labelFormatter={(label: string) =>
            new Date(label).toLocaleDateString("en-IN", {
              day: "2-digit",
              month: "short",
              year: "numeric",
            })
          }
          formatter={(value: number, name: string) => [formatValue(value), name]}
        />
        {showLegend ? (
          <Legend
            verticalAlign="top"
            height={28}
            iconType="plainline"
            wrapperStyle={{ fontSize: 12, color: "#6B6560" }}
          />
        ) : null}
        {series.map((s) =>
          s.area ? (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              fill={s.color}
              fillOpacity={0.1}
              strokeWidth={1.8}
              dot={false}
              connectNulls
            />
          ) : (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={1.8}
              strokeDasharray={s.dashed ? "4 3" : undefined}
              dot={false}
              connectNulls
            />
          ),
        )}
      </ComposedChart>
    </ResponsiveContainer>
  
      <DataProvenanceTag compact />
    </div>
  );
}
