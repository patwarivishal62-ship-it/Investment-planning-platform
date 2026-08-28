"use client";

import { useState } from "react";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Correlation heatmap. Colour is explicitly bipolar (teal negative -> neutral ->
 * indigo positive) and every cell also carries its numeric value, so the
 * information is never colour-only (accessibility requirement).
 */
export function CorrelationHeatmap({
  symbols,
  matrix,
  maxSymbols = 26,
}: {
  symbols: string[];
  matrix: (number | null)[][];
  maxSymbols?: number;
}) {
  const [hovered, setHovered] = useState<{ row: number; col: number } | null>(null);
  const shown = symbols.slice(0, maxSymbols);
  const size = shown.length;

  const color = (value: number | null) => {
    if (value == null || !Number.isFinite(value)) return "#F5F5F4";
    // -1 -> teal, 0 -> near white, +1 -> indigo
    const intensity = Math.min(Math.abs(value), 1);
    if (value < 0) return `rgba(15, 118, 110, ${0.08 + intensity * 0.72})`;
    return `rgba(67, 56, 202, ${0.06 + intensity * 0.72})`;
  };

  const textColor = (value: number | null) =>
    value != null && Math.abs(value) > 0.55 ? "#FFFFFF" : "#44403C";

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full border-separate" style={{ borderSpacing: 2 }}>
        <caption className="sr-only">
          Pearson correlation matrix of daily returns over the selected period. Values range from
          minus one to plus one.
        </caption>
        <thead>
          <tr>
            <th />
            {shown.map((symbol) => (
              <th
                key={symbol}
                scope="col"
                className="px-0.5 pb-1 text-[0.6rem] font-medium text-ink-subtle"
                style={{ writingMode: "vertical-rl", height: 68 }}
              >
                {symbol}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((rowSymbol, row) => (
            <tr key={rowSymbol}>
              <th
                scope="row"
                className="whitespace-nowrap pr-2 text-right text-[0.68rem] font-medium text-ink-muted"
              >
                {rowSymbol}
              </th>
              {shown.map((colSymbol, col) => {
                const value = matrix?.[row]?.[col] ?? null;
                const active =
                  hovered && (hovered.row === row || hovered.col === col);
                return (
                  <td
                    key={colSymbol}
                    className={cn(
                      "num h-6 text-center text-[0.62rem] transition-opacity",
                      active ? "opacity-100" : hovered ? "opacity-45" : "opacity-100",
                    )}
                    style={{ background: color(value), color: textColor(value) }}
                    onMouseEnter={() => setHovered({ row, col })}
                    onMouseLeave={() => setHovered(null)}
                    title={`${rowSymbol} vs ${colSymbol}: ${value == null ? "n/a" : formatNumber(value, 2)}`}
                  >
                    {value == null ? "" : formatNumber(value, 2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {size === 0 ? <p className="py-6 text-center text-sm text-ink-muted">No correlation data.</p> : null}
      <div className="mt-3 flex items-center gap-3 text-[0.7rem] text-ink-subtle">
        <span>-1.0</span>
        <span
          className="h-2 flex-1 rounded"
          style={{
            background:
              "linear-gradient(to right, #0F766E, #F5F5F4 50%, #4338CA)",
          }}
        />
        <span>+1.0</span>
        <span className="ml-2">Negative (diversifying) ← → Positive (moves together)</span>
      </div>
    </div>
  );
}
