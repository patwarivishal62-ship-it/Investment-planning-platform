"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Plan, RecommendResponse } from "@/types";

export interface InvestorProfile {
  initialInvestment: number;
  monthlyContribution: number;
  annualContributionIncrease: number;
  horizonYears: number;
  objective: string;
  secondaryObjective?: string;
  riskScore: number;
  riskBand: string;
  answers: Record<string, string>;
}

export interface ConstraintsState {
  maxWeight: number;
  minWeight: number;
  maxVolatility: number | null;
  maxDrawdown: number | null;
  maxPositions: number;
  excluded: string[];
  classBounds: Record<string, [number, number | null]>;
}

export const DEFAULT_PROFILE: InvestorProfile = {
  initialInvestment: 1_000_000,
  monthlyContribution: 20_000,
  annualContributionIncrease: 0,
  horizonYears: 10,
  objective: "wealth_creation",
  riskScore: 55,
  riskBand: "Moderate",
  answers: {},
};

export const DEFAULT_CONSTRAINTS: ConstraintsState = {
  maxWeight: 0.4,
  minWeight: 0,
  maxVolatility: null,
  maxDrawdown: null,
  maxPositions: 12,
  excluded: [],
  classBounds: {},
};

interface AppState {
  profile: InvestorProfile;
  setProfile: (profile: Partial<InvestorProfile>) => void;
  resetProfile: () => void;
  constraints: ConstraintsState;
  setConstraints: (constraints: Partial<ConstraintsState>) => void;
  universe: string[];
  setUniverse: (symbols: string[]) => void;
  plans: Plan[];
  setPlans: (plans: Plan[], meta?: RecommendResponse | null) => void;
  recommendations: RecommendResponse | null;
  compare: string[];
  toggleCompare: (planId: string) => void;
  hydrated: boolean;
}

const STORAGE_KEY = "quant-planner-state-v1";

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfileState] = useState<InvestorProfile>(DEFAULT_PROFILE);
  const [constraints, setConstraintsState] = useState<ConstraintsState>(DEFAULT_CONSTRAINTS);
  const [universe, setUniverseState] = useState<string[]>([]);
  const [plans, setPlansState] = useState<Plan[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendResponse | null>(null);
  const [compare, setCompare] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);

  // Restore on mount (client only) so the user's plan survives a refresh.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<{
          profile: InvestorProfile;
          constraints: ConstraintsState;
          universe: string[];
          plans: Plan[];
          recommendations: RecommendResponse | null;
          compare: string[];
        }>;
        if (parsed.profile) setProfileState({ ...DEFAULT_PROFILE, ...parsed.profile });
        if (parsed.constraints) setConstraintsState({ ...DEFAULT_CONSTRAINTS, ...parsed.constraints });
        if (parsed.universe) setUniverseState(parsed.universe);
        if (parsed.plans) setPlansState(parsed.plans);
        if (parsed.recommendations) setRecommendations(parsed.recommendations);
        if (parsed.compare) setCompare(parsed.compare);
      }
    } catch {
      // Corrupt or unavailable storage is not worth failing the app for.
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ profile, constraints, universe, plans, recommendations, compare }),
      );
    } catch {
      // Storage quota exceeded (large plan payloads) -- degrade silently.
    }
  }, [hydrated, profile, constraints, universe, plans, recommendations, compare]);

  const setProfile = useCallback((patch: Partial<InvestorProfile>) => {
    setProfileState((current) => ({ ...current, ...patch }));
  }, []);

  const resetProfile = useCallback(() => setProfileState(DEFAULT_PROFILE), []);

  const setConstraints = useCallback((patch: Partial<ConstraintsState>) => {
    setConstraintsState((current) => ({ ...current, ...patch }));
  }, []);

  const setUniverse = useCallback((symbols: string[]) => setUniverseState(symbols), []);

  const setPlans = useCallback((next: Plan[], meta: RecommendResponse | null = null) => {
    setPlansState(next);
    setRecommendations(meta);
  }, []);

  const toggleCompare = useCallback((planId: string) => {
    setCompare((current) =>
      current.includes(planId)
        ? current.filter((id) => id !== planId)
        : current.length >= 5
          ? current
          : [...current, planId],
    );
  }, []);

  const value = useMemo<AppState>(
    () => ({
      profile,
      setProfile,
      resetProfile,
      constraints,
      setConstraints,
      universe,
      setUniverse,
      plans,
      setPlans,
      recommendations,
      compare,
      toggleCompare,
      hydrated,
    }),
    [profile, setProfile, resetProfile, constraints, setConstraints, universe, setUniverse,
     plans, setPlans, recommendations, compare, toggleCompare, hydrated],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be used inside <AppProvider>");
  return context;
}

/** Build the recommend payload from profile + constraints + universe. */
export function buildRecommendPayload(
  profile: InvestorProfile,
  constraints: ConstraintsState,
  universe: string[],
  overrides: Partial<Record<string, unknown>> = {},
) {
  return {
    capital: profile.initialInvestment,
    monthlyContribution: profile.monthlyContribution,
    annualContributionIncrease: profile.annualContributionIncrease,
    horizonYears: profile.horizonYears,
    riskScore: profile.riskScore,
    objective: profile.objective,
    secondaryObjective: profile.secondaryObjective,
    maxWeight: constraints.maxWeight,
    minWeight: constraints.minWeight,
    maxVolatility: constraints.maxVolatility,
    maxDrawdown: constraints.maxDrawdown,
    maxPositions: constraints.maxPositions,
    excluded: constraints.excluded,
    classBounds: Object.keys(constraints.classBounds).length ? constraints.classBounds : undefined,
    symbols: universe.length ? universe : undefined,
    ...overrides,
  };
}
