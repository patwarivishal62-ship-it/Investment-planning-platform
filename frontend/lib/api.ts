/**
 * Typed API client.
 *
 * The browser only ever requests the RELATIVE path /api/... -- Next.js proxies
 * it to the FastAPI backend (see next.config.mjs). No backend host is ever
 * exposed to the client, and no provider credentials can leak through it.
 */
import type {
  Asset,
  BacktestResult,
  DataStatus,
  FrontierResponse,
  MonteCarloResponse,
  Objective,
  Plan,
  PortfolioMetrics,
  Question,
  RecommendResponse,
  RiskProfileResult,
  StressScenario,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export class ApiRequestError extends Error {
  code: string;
  suggestions: string[];
  detail: Record<string, unknown> | undefined;
  status: number;

  constructor(
    message: string,
    status: number,
    code = "request_failed",
    suggestions: string[] = [],
    detail?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.suggestions = suggestions;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const { json, ...rest } = init ?? {};
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(rest.headers ?? {}),
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      cache: "no-store",
    });
  } catch {
    throw new ApiRequestError(
      "Could not reach the analytics service. Check that the backend is running.",
      0,
      "network_error",
      ["Start the backend (see README) and retry."],
    );
  }

  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const body = (payload ?? {}) as {
      detail?: unknown;
      error?: string;
      code?: string;
      suggestions?: string[];
    };
    // FastAPI validation errors arrive as {detail: [...]}; our own handlers
    // return a flat envelope with `error`, `code` and `suggestions`.
    const detail = body.detail;
    if (body.error || body.code) {
      throw new ApiRequestError(
        body.error ?? "Request failed.",
        response.status,
        body.code,
        body.suggestions ?? [],
        typeof detail === "object" && detail !== null ? (detail as Record<string, unknown>) : undefined,
      );
    }
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string; loc?: (string | number)[] } | undefined;
      throw new ApiRequestError(
        first?.msg ?? "The request was invalid.",
        response.status,
        "validation_error",
      );
    }
    throw new ApiRequestError(
      typeof detail === "string" ? detail : "Request failed.",
      response.status,
    );
  }
  return payload as T;
}

const post = <T>(path: string, json?: unknown) =>
  request<T>(path, { method: "POST", json: json ?? {} });

export const api = {
  // ---- system ----
  status: () => request<DataStatus>("/data/status"),
  config: () =>
    request<Record<string, number | string | boolean>>("/config"),

  // ---- assets & analytics ----
  assets: () => request<Asset[]>("/assets"),
  analytics: (body: { symbols?: string[]; start?: string; end?: string }) =>
    post<{
      assets: Record<string, unknown>[];
      symbols: string[];
      correlation: { symbols: string[]; matrix: (number | null)[][]; averagePairwiseCorrelation: number };
      pca: Record<string, unknown>;
      period: { start: string; end: string };
      dataQuality: { score: number; grade: string; issues: string[] };
    }>("/analytics/assets", body),
  correlation: (body: {
    symbols?: string[];
    start?: string;
    end?: string;
    window?: number;
    rollingSymbol?: string;
    rollingSymbolB?: string;
    rollingWindow?: number;
  }) =>
    post<{
      symbols: string[];
      matrix: (number | null)[][];
      averagePairwiseCorrelation: number;
      windowDays: number;
      period: { start: string; end: string };
      rolling?: { date: string; value: number }[];
    }>("/analytics/correlation", body),

  // ---- portfolio ----
  analyze: (body: Record<string, unknown>) => post<PortfolioMetrics>("/portfolio/analyze", body),
  whatIf: (body: Record<string, unknown>) => post<{ metrics: PortfolioMetrics; assumptions: Record<string, unknown> }>("/portfolio/what-if", body),
  riskContribution: (body: Record<string, unknown>) =>
    post<{ portfolioVolatility: number; contributions: PortfolioMetrics["riskContribution"]; assumptions: Record<string, unknown> }>(
      "/portfolio/risk-contribution",
      body,
    ),
  diversification: (body: Record<string, unknown>) =>
    post<{
      steps: { label: string; metrics: Record<string, number>; volatilityChange?: number; drawdownChange?: number; sharpeChange?: number; weights?: Record<string, number> }[];
      period: string;
      assumptions: Record<string, unknown>;
    }>("/portfolio/diversification", body),
  advanced: (body: Record<string, unknown>) => post<Record<string, unknown>>("/portfolio/advanced", body),

  // ---- optimization ----
  optimize: (body: Record<string, unknown>) =>
    post<{ results: { strategy: string; metrics: PortfolioMetrics }[]; feasibility: Record<string, unknown>; assumptions: Record<string, unknown> }>(
      "/portfolio/optimize",
      body,
    ),
  recommend: (body: Record<string, unknown>) => post<RecommendResponse>("/portfolio/recommend", body),
  frontier: (body: Record<string, unknown>) => post<FrontierResponse>("/efficient-frontier", body),

  // ---- simulation ----
  backtest: (body: Record<string, unknown>) =>
    post<{
      portfolio: BacktestResult;
      benchmarks: (BacktestResult & { symbol: string; name: string; equityCurve: number[] })[];
      assumptions: Record<string, unknown>;
    }>("/backtest", body),
  rebalance: (body: Record<string, unknown>) =>
    post<{ results: BacktestResult[]; assumptions: Record<string, unknown> }>("/backtest/rebalance", body),
  walkForward: (body: Record<string, unknown>) =>
    post<{
      strategy: string;
      weights: Record<string, number>;
      inSample: BacktestResult;
      outOfSample: BacktestResult;
      benchmarkOutOfSample: BacktestResult | null;
      trainEnd: string;
      assumptions: Record<string, unknown>;
    }>("/backtest/walk-forward", body),
  monteCarlo: (body: Record<string, unknown>) => post<MonteCarloResponse>("/monte-carlo", body),
  stressTest: (body: Record<string, unknown>) =>
    post<{
      scenarios: StressScenario[];
      historicalWindows: { label: string; startDate: string; endDate: string; return: number; windowDays: number }[];
      portfolioValue: number;
      weights: Record<string, number>;
      assumptions: Record<string, unknown>;
    }>("/stress-test", body),

  // ---- profile ----
  questions: () =>
    request<{
      questions: Question[];
      objectives: Objective[];
      horizons: { id: string; label: string; years: number }[];
      bands: { max: number; label: string }[];
    }>("/profile/questions"),
  riskScore: (answers: Record<string, string>) => post<RiskProfileResult>("/profile/risk-score", { answers }),
};

export type { Plan };
