"use client";

import { cn } from "@/lib/utils";
import { useDataStatus } from "@/lib/hooks/useDataStatus";

/**
 * Small provenance tag. The spec requires that every chart built on demo data
 * says so on its own face, not only in a page-level banner -- a chart can be
 * screenshotted, exported or scrolled past on its own.
 */
export function DataProvenanceTag({ compact = false }: { compact?: boolean }) {
  const status = useDataStatus();
  if (!status?.isDemo) return null;

  return (
    <span
      title="Demo data is synthetic and generated from a seeded model. It is not live or historical market data."
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded border border-amber-300 bg-amber-50 font-medium uppercase tracking-wide text-amber-800",
        compact ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]",
      )}
    >
      <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" aria-hidden>
        <circle cx="4" cy="4" r="4" />
      </svg>
      Demo data — not live market data
    </span>
  );
}

/** Every chart is wrapped in a labelled, downloadable frame (spec section 37). */
export function ChartFrame({
  title,
  subtitle,
  action,
  height = 280,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  height?: number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("w-full", className)}>
      {title ? (
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-ink">{title}</h3>
            {subtitle ? <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      <div style={{ height }} className="w-full">
        {children}
      </div>
    </div>
  );
}

/** Download the data behind a chart as CSV (spec: "downloadable data"). */
export function downloadCsv(filename: string, rows: (string | number | null)[][], header: string[]) {
  const escape = (value: string | number | null) => {
    const text = value == null ? "" : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = [header, ...rows].map((row) => row.map(escape).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export const AXIS_STYLE = { fontSize: 11, fill: "#8F8781" } as const;
export const GRID_COLOR = "#EFEDEA";
