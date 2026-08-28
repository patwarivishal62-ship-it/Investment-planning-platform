"use client";

import { useMemo } from "react";
import { api } from "@/lib/api";
import { useApi } from "./useApi";
import type { Asset } from "@/types";

/** Shared asset metadata (symbol -> class, name) used by every portfolio view. */
export function useAssets() {
  const { data, error, loading } = useApi<Asset[]>(() => api.assets(), []);

  const classOf = useMemo(() => {
    const map: Record<string, string> = {};
    for (const asset of data ?? []) map[asset.symbol] = asset.assetClass;
    return map;
  }, [data]);

  const names = useMemo(() => {
    const map: Record<string, string> = {};
    for (const asset of data ?? []) map[asset.symbol] = asset.name;
    return map;
  }, [data]);

  return { assets: data ?? [], classOf, names, error, loading };
}
