"use client";

import { formatDate, formatPercent } from "@/lib/format";
import type { Assumptions } from "@/types";

/** Transparency strip (spec section 51): period, rebalance, rf, costs, quality. */
export function AssumptionBar({
  assumptions,
  mode,
  extra = [],
}: {
  assumptions?: Assumptions;
  mode?: string;
  extra?: { label: string; value: string }[];
}) {
  if (!assumptions && !extra.length) return null;
  const items: { label: string; value: string }[] = [];

  if (assumptions?.dataPeriod) items.push({ label: "Data period", value: assumptions.dataPeriod });
  if (typeof assumptions?.riskFreeRate === "number")
    items.push({ label: "Risk-free rate", value: formatPercent(assumptions.riskFreeRate) });
  if (assumptions?.rebalance)
    items.push({ label: "Rebalance", value: String(assumptions.rebalance) });
  if (typeof assumptions?.transactionCostsBps === "number")
    items.push({
      label: "Transaction costs",
      value: `${Number(assumptions.transactionCostsBps).toFixed(0)} bps`,
    });
  if (typeof assumptions?.candidates === "number")
    items.push({
      label: "Candidates analysed",
      value: Number(assumptions.candidates).toLocaleString("en-IN"),
    });
  if (typeof assumptions?.dataQualityScore === "number")
    items.push({ label: "Data quality", value: `${assumptions.dataQualityScore}/100` });
  if (typeof assumptions?.observations === "number")
    items.push({
      label: "Observations",
      value: Number(assumptions.observations).toLocaleString("en-IN"),
    });
  if (mode) items.push({ label: "Data mode", value: mode });
  items.push(...extra);

  return (
    <div className="rounded-lg border border-line bg-stone-50 px-3 py-2.5">
      <dl className="flex flex-wrap gap-x-6 gap-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-baseline gap-1.5">
            <dt className="text-[0.7rem] uppercase tracking-wide text-ink-subtle">{item.label}</dt>
            <dd className="text-[0.75rem] font-medium text-ink">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function SourceNote({ text }: { text: string }) {
  return (
    <p className="text-xs leading-relaxed text-ink-subtle">
      {text} · Source and timestamp of the underlying data are shown under the data status
      indicator in the header.
    </p>
  );
}

export { formatDate };
