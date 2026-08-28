"use client";

import { useState } from "react";
import { useDataStatus } from "@/lib/hooks/useDataStatus";
import { formatDateTime } from "@/lib/format";
import type { DataStatus } from "@/types";
import { cn } from "@/lib/utils";

const TONE: Record<string, { dot: string; text: string; label: string }> = {
  demo: { dot: "bg-amber-500", text: "text-amber-800", label: "Demo Data" },
  live: { dot: "bg-teal-600", text: "text-teal-800", label: "Live Data" },
  cached: { dot: "bg-indigo-600", text: "text-indigo-800", label: "Cached Data" },
  unavailable: { dot: "bg-rose-600", text: "text-rose-800", label: "Unavailable" },
};

/**
 * Data provenance indicator (spec section 72). Clicking it exposes provider,
 * timestamp, asset count, history range and data quality -- the user can always
 * tell whether they are looking at demo, live or cached data.
 */
export function DataStatusIndicator() {
  const status = useDataStatus();
  const [open, setOpen] = useState(false);

  const tone = TONE[status?.mode ?? "unavailable"] ?? TONE.unavailable;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={cn(
          "flex items-center gap-2 rounded-full border border-line bg-surface px-2.5 py-1 text-xs font-medium transition-colors hover:bg-stone-50",
          tone.text,
        )}
      >
        <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />
        {tone.label}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-30" aria-hidden onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-80 animate-fade-in rounded-xl border border-line bg-surface p-4 shadow-raised">
            <h3 className="text-sm font-semibold text-ink">Market data source</h3>
            {status ? (
              <dl className="mt-3 space-y-2 text-xs">
                <Row label="Provider" value={status.provider} />
                <Row label="Mode" value={tone.label} />
                <Row label="Last updated" value={formatDateTime(status.lastUpdated)} />
                <Row label="Assets" value={String(status.assetCount ?? "—")} />
                <Row
                  label="History"
                  value={
                    status.historyStart && status.historyEnd
                      ? `${status.historyStart} → ${status.historyEnd}`
                      : "—"
                  }
                />
                {status.dataQuality ? (
                  <Row
                    label="Data quality"
                    value={`${status.dataQuality.score}/100 (${status.dataQuality.grade})`}
                  />
                ) : null}
              </dl>
            ) : (
              <p className="mt-2 text-xs text-ink-muted">Status unavailable.</p>
            )}
            {status?.isDemo ? (
              <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-[0.7rem] leading-relaxed text-amber-900">
                Demo data is synthetic and generated from a seeded model. It is not live or
                historical market data and must not be used for real investment decisions.
              </p>
            ) : null}
            {status?.warnings?.length ? (
              <ul className="mt-3 space-y-1">
                {status.warnings.map((warning) => (
                  <li key={warning} className="text-[0.7rem] leading-relaxed text-ink-subtle">
                    • {warning}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-ink-subtle">{label}</dt>
      <dd className="text-right font-medium text-ink">{value}</dd>
    </div>
  );
}
