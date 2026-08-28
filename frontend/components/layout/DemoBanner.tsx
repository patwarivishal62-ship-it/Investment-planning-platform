"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Persistent, unmissable label whenever the data behind a page is synthetic. */
export function DemoBanner() {
  const [isDemo, setIsDemo] = useState<boolean | null>(null);

  useEffect(() => {
    api.status().then((status) => setIsDemo(status.isDemo)).catch(() => setIsDemo(null));
  }, []);

  if (!isDemo) return null;
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
