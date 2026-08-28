"use client";

import { cn } from "@/lib/utils";

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
          <div>
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
