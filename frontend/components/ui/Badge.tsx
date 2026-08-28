import { cn } from "@/lib/utils";

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "accent" | "positive" | "caution" | "negative";
  className?: string;
}) {
  const tones = {
    neutral: "border-stone-200 bg-stone-50 text-stone-700",
    accent: "border-indigo-200 bg-indigo-50 text-indigo-800",
    positive: "border-teal-200 bg-teal-50 text-teal-800",
    caution: "border-amber-200 bg-amber-50 text-amber-800",
    negative: "border-rose-200 bg-rose-50 text-rose-800",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[0.7rem] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
