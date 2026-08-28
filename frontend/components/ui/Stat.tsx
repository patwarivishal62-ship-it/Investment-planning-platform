import { cn } from "@/lib/utils";

/** A single metric. `hint` drives the small methodology tooltip. */
export function Stat({
  label,
  value,
  sub,
  tone,
  hint,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "default" | "positive" | "negative" | "caution";
  hint?: string;
  className?: string;
}) {
  const tones = {
    default: "text-ink",
    positive: "text-positive",
    negative: "text-negative",
    caution: "text-caution",
  } as const;
  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-center gap-1">
        <span className="label truncate">{label}</span>
        {hint ? (
          <span className="cursor-help text-ink-subtle" title={hint} aria-label={hint}>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
              <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM7.25 4.5h1.5v1.5h-1.5V4.5zm0 3h1.5v4h-1.5v-4z" />
            </svg>
          </span>
        ) : null}
      </div>
      <div className={cn("num mt-1 truncate text-xl font-semibold tracking-tight", tones[tone ?? "default"])}>
        {value}
      </div>
      {sub ? <div className="mt-0.5 truncate text-xs text-ink-subtle">{sub}</div> : null}
    </div>
  );
}
