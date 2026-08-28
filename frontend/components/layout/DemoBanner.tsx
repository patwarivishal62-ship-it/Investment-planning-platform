"use client";

import { useDataStatus } from "@/lib/hooks/useDataStatus";

/** Persistent, unmissable label whenever the data behind a page is synthetic. */
export function DemoBanner() {
  const status = useDataStatus();

  if (!status?.isDemo) return null;
  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto max-w-7xl px-4 py-2 sm:px-6">
        <p className="text-xs font-medium text-amber-900">
          Demo data — not live market data. All figures are generated from a seeded synthetic
          model for demonstration purposes.
        </p>
      </div>
    </div>
  );
}
