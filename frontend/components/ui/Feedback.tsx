import { cn } from "@/lib/utils";
import { Button } from "./Button";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-stone-300 border-t-accent-700",
        className,
      )}
    />
  );
}

/** Shown for slow, genuinely expensive computations (spec section 69). */
export function ProgressNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-accent-100 bg-accent-50 px-4 py-3 text-sm text-accent-800">
      <Spinner className="border-accent-200 border-t-accent-700" />
      <span>{children}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      {icon ? <div className="text-ink-subtle">{icon}</div> : null}
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description ? <p className="max-w-md text-sm text-ink-muted">{description}</p> : null}
      {action}
    </div>
  );
}

export function ErrorState({
  title,
  message,
  suggestions,
  onRetry,
}: {
  title?: string;
  message: string;
  suggestions?: string[];
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-5">
      <h3 className="text-sm font-semibold text-rose-900">{title ?? "Something went wrong"}</h3>
      <p className="mt-1 text-sm text-rose-800">{message}</p>
      {suggestions?.length ? (
        <ul className="mt-3 space-y-1.5">
          {suggestions.map((suggestion) => (
            <li key={suggestion} className="flex gap-2 text-sm text-rose-900">
              <span aria-hidden className="select-none text-rose-400">
                →
              </span>
              <span>{suggestion}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
