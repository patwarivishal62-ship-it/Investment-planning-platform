"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { AXIS_STYLE, GRID_COLOR } from "./ChartFrame";
import { formatNumber, formatPercent } from "@/lib/format";
import { DataProvenanceTag } from "./ChartFrame";

export interface FrontierPointInput {
  expectedReturn: number;
  volatility: number;
}

/**
 * Efficient frontier: volatility on X, expected return on Y, with the
 * minimum-variance and maximum-Sharpe portfolios highlighted.
 */
export function EfficientFrontierChart({
  points,
  minVariance,
  tangency,
  selected,
  height = 340,
  onSelect,
}: {
  points: FrontierPointInput[];
  minVariance?: FrontierPointInput | null;
  tangency?: FrontierPointInput | null;
  selected?: FrontierPointInput | null;
  height?: number;
  onSelect?: (point: FrontierPointInput) => void;
}) {
  const curve = points.map((point, index) => ({ ...point, index }));
  const data = curve.length ? curve : [{ expectedReturn: 0, volatility: 0 }];

  return (
    <div className="w-full">

    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 20, left: 4 }}>
        <CartesianGrid stroke={GRID_COLOR} />
        <XAxis
          type="number"
          dataKey="volatility"
          name="Volatility"
          tick={AXIS_STYLE}
          tickFormatter={(value: number) => formatPercent(value, 1)}
          stroke="#DAD6D2"
          label={{
            value: "Annualised volatility",
            position: "insideBottom",
            offset: -12,
            style: { fontSize: 11, fill: "#8F8781" },
          }}
        />
        <YAxis
          type="number"
          dataKey="expectedReturn"
          name="Expected return"
          tick={AXIS_STYLE}
          tickFormatter={(value: number) => formatPercent(value, 1)}
          stroke="#DAD6D2"
          width={58}
        />
        <ZAxis range={[40, 40]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          contentStyle={{
            borderRadius: 8,
            border: "1px solid #E7E5E4",
            fontSize: 12,
            boxShadow: "0 4px 12px -2px rgb(28 25 23 / 0.08)",
          }}
          formatter={(value: number, name: string) => [formatPercent(value, 2), name]}
        />
        <Scatter
          name="Efficient frontier"
          data={data}
          fill="#4338CA"
          line={{ stroke: "#4338CA", strokeWidth: 2 }}
          shape="circle"
          onClick={(event) => {
            const payload = (event as unknown as { payload?: FrontierPointInput })?.payload;
            if (payload && onSelect) onSelect(payload);
          }}
        />
        {minVariance ? (
          <Scatter
            name="Minimum variance"
            data={[{ ...minVariance }]}
            fill="#0F766E"
            shape="diamond"
          />
        ) : null}
        {tangency ? (
          <Scatter name="Maximum Sharpe" data={[{ ...tangency }]} fill="#B45309" shape="star" />
        ) : null}
        {selected ? (
          <Scatter name="Your portfolio" data={[{ ...selected }]} fill="#BE185D" shape="triangle" />
        ) : null}
      </ScatterChart>
    </ResponsiveContainer>
  
      <DataProvenanceTag compact />
    </div>
  );
}

export function frontierTooltipRows(point: FrontierPointInput, sharpe?: number) {
  return [
    { label: "Expected return", value: formatPercent(point.expectedReturn, 2) },
    { label: "Volatility", value: formatPercent(point.volatility, 2) },
    ...(sharpe !== undefined ? [{ label: "Sharpe", value: formatNumber(sharpe, 2) }] : []),
  ];
}
