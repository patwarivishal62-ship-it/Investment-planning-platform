"use client";

import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Horizontal bar list used for risk contribution and asset-class exposure. */
export function BarList({
  items,
  valueFormat = "percent",
  color = "#4338CA",
  secondary,
}: {
  items: { key: string; label: string; value: number; secondaryValue?: number; secondaryLabel?: string }[];
  valueFormat?: "percent" | "number";
  color?: string;
  secondary?: string;
}) {
  const max = Math.max(...items.map((item) => Math.abs(item.value)), 0.0001);
  const format = (value: number) =>
    valueFormat === "percent" ? formatPercent(value, 1) : value.toFixed(2);

  return (
    <ul className="space-y-2.5">
      {items.map((item) => (
        <li key={item.key}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate text-ink">{item.label}</span>
            <span className="num shrink-0 font-medium text-ink">
              {format(item.value)}
              {item.secondaryValue !== undefined ? (
                <span className="ml-2 text-xs font-normal text-ink-subtle">
                  {item.secondaryLabel}: {format(item.secondaryValue)}
                </span>
              ) : null}
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-stone-100">
            <div
              className={cn("h-full rounded-full")}
              style={{
                width: `${(Math.abs(item.value) / max) * 100}%`,
                background: color,
              }}
            />
          </div>
        </li>
      ))}
      {secondary ? <li className="pt-1 text-xs text-ink-subtle">{secondary}</li> : null}
    </ul>
  );
}
