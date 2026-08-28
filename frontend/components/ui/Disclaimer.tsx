import { cn } from "@/lib/utils";

/**
 * Compliance surface. Every analytical view carries one of these so the product
 * is never mistaken for advice or a promise of returns (spec sections 52-53).
 */
export function Disclaimer({
  children,
  className,
  variant = "note",
}: {
  children: React.ReactNode;
  className?: string;
  variant?: "note" | "strong";
}) {
  return (
    <p
      className={cn(
        "text-xs leading-relaxed",
        variant === "strong"
          ? "rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900"
          : "text-ink-subtle",
        className,
      )}
    >
      {children}
    </p>
  );
}

export const SHORT_DISCLAIMER =
  "Analytical and educational tool only. Model-estimated figures from historical data — not advice, not a guarantee, and not a prediction of future results.";
