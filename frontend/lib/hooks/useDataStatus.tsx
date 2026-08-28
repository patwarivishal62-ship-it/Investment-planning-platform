"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DataStatus } from "@/types";

/**
 * Data provenance, shared by every component that needs it (banner, nav
 * indicator, and each chart's provenance tag).
 *
 * Two goals that pull in opposite directions:
 *
 * 1. The label must be present in the very first paint. A chart must never be
 *    on screen, even briefly, without saying whether its data is synthetic --
 *    so the root layout (a server component) fetches the status and passes it
 *    down as the seed value.
 * 2. It must not go stale. A page prerendered at build time would otherwise
 *    bake in whatever mode the backend happened to be in, so the client
 *    revalidates on mount and any component can call `invalidateDataStatus`
 *    (e.g. after the user switches provider).
 */
const DataStatusContext = createContext<DataStatus | null>(null);

export function DataStatusProvider({
  initialStatus,
  children,
}: {
  initialStatus: DataStatus | null;
  children: React.ReactNode;
}) {
  const [status, setStatus] = useState<DataStatus | null>(initialStatus);

  useEffect(() => {
    // Refresh on mount so a prerendered seed cannot linger.
    let cancelled = false;
    api
      .status()
      .then((fresh) => {
        if (!cancelled) setStatus(fresh);
      })
      .catch(() => {
        // Keep the seed rather than clearing it and losing the label.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <DataStatusContext.Provider value={status}>{children}</DataStatusContext.Provider>;
}

export function useDataStatus(): DataStatus | null {
  return useContext(DataStatusContext);
}

/** Re-fetch the status everywhere, e.g. after the user switches provider. */
export function invalidateDataStatus() {
  api
    .status()
    .then(() => {
      // Components read through context; a full reload keeps this simple and
      // avoids a second source of truth.
      window.location.reload();
    })
    .catch(() => {
      window.location.reload();
    });
}
