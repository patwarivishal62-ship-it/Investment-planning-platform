/** Shared domain types mirroring the backend schemas. */

export type AssetClass =
  | "equity"
  | "bond"
  | "gold"
  | "silver"
  | "commodity"
  | "international_equity"
  | "reit"
  | "cash";

export interface Asset {
  symbol: string;
  name: string;
  assetClass: AssetClass;
  country: string;
  sector: string;
  currency: string;
  dataSource: string;
  liquidity: number;
  available?: boolean;
  price?: number | null;
  asOf?: string | null;
  historyDays?: number;
  historyStart?: string | null;
  historyEnd?: string | null;
  annualizedReturn?: number | null;
  volatility?: number | null;
  sharpe?: number | null;
  sortino?: number | null;
  maxDrawdown?: number | null;
  avgCorrelation?: number | null;
  dataQuality?: number | null;
}

export interface RiskComponent {
  key: string;
  weight: number;
  normalized: number;
  contribution: number;
}

export interface RiskScore {
  score: number;
  band: string;
  components: RiskComponent[];
  inputs: Record<string, number>;
}

export interface RiskContributionRow {
  symbol: string;
  name: string;
  assetClass: string;
  weight: number;
  volatility: number;
  marginalRiskContribution: number;
  riskContribution: number;
  riskShare: number;
}

export interface PortfolioMetrics {
  weights: Record<string, number>;
  expectedReturn: number;
  cagr: number;
  volatility: number;
  sharpe: number;
  sharpeOnCagr: number;
  sortino: number;
  calmar: number;
  maxDrawdown: number;
  downsideDeviation: number;
  ulcerIndex: number;
  historicalVaR: number;
  historicalCVaR: number;
  parametricVaR: number;
  parametricCVaR: number;
  skewness: number;
  kurtosis: number;
  bestPeriod: number;
  worstPeriod: number;
  positivePeriods: number;
  recoveryPeriods: number | null;
  diversificationRatio: number;
  effectiveAssets: number;
  herfindahlIndex: number;
  assetClassExposure: Record<string, number>;
  weightedLiquidity: number;
  riskScore: RiskScore;
  observations: number;
  equityCurve?: number[];
  performanceCurve?: number[];
  dates?: string[];
  drawdownSeries?: number[];
  drawdowns?: DrawdownEpisode[];
  riskContribution?: RiskContributionRow[];
  returnContribution?: { symbol: string; weight: number; contribution: number; share: number }[];
  correlationMatrix?: (number | null)[][];
  covarianceMatrix?: (number | null)[][];
  symbols?: string[];
  assetMetrics?: Record<string, number | string>[];
  assumptions?: Assumptions;
}

export interface DrawdownEpisode {
  depth: number;
  peakIndex: number;
  troughIndex: number;
  recoveryIndex: number | null;
  lengthPeriods: number;
  recoveryPeriods: number | null;
  recovered: boolean;
  peakDate: string | null;
  troughDate: string | null;
  recoveryDate: string | null;
}

export interface Assumptions {
  riskFreeRate?: number;
  tradingDaysPerYear?: number;
  varConfidence?: number;
  dataPeriod?: string;
  dataStart?: string;
  dataEnd?: string;
  observations?: number;
  dataQualityScore?: number;
  rebalance?: string;
  transactionCostsBps?: number;
  candidates?: number;
  maxPositions?: number;
  minHoldingWeight?: number;
  [key: string]: unknown;
}

export interface PlanExplanation {
  summary: string;
  objective: string;
  returnDriver: { text: string; assets: { symbol: string; name: string; weight: number; shareOfReturn: number }[] };
  riskReducer: {
    text: string;
    assets: { symbol: string; name: string; weight: number; riskShare: number; correlationToPortfolio: number; relief: number }[];
  };
  diversification: { text: string; effectiveAssets: number; diversificationRatio: number; largestAssetClass: string | null };
  mainRisk: { text: string; assets: { symbol: string; name: string; weight: number; riskShare: number }[] };
  caveat: string;
}

export interface Plan {
  id: string;
  name: string;
  summary: string;
  bestFit: boolean;
  score: number;
  fitScore: number;
  subScores: Record<string, number>;
  metrics: PortfolioMetrics;
  explanation: PlanExplanation;
  positions?: number;
}

export interface RecommendResponse {
  plans: Plan[];
  objective: string;
  riskScore: number;
  candidateCount: number;
  evaluatedCount: number;
  feasibility: Record<string, unknown>;
  scoringWeights: Record<string, number>;
  assumptions: Assumptions;
}

export interface DataStatus {
  mode: "demo" | "live" | "cached" | "unavailable";
  provider: string;
  lastUpdated: string | null;
  assetCount: number;
  historyStart?: string | null;
  historyEnd?: string | null;
  observations?: number;
  isDemo: boolean;
  warnings: string[];
  dataQuality?: {
    score: number;
    grade: string;
    issues: string[];
    quarantined: string[];
    coverage?: Record<string, number | string>;
  } | null;
}

export interface FrontierPoint {
  expectedReturn: number;
  volatility: number;
}

export interface FrontierResponse {
  points: FrontierPoint[];
  minVariance: FrontierPoint;
  maxReturn: { expectedReturn: number; volatility: number | null };
  tangency: FrontierPoint | null;
  riskFreeRate: number;
  symbols: string[];
  assumptions: Assumptions;
}

export interface QuestionOption {
  id: string;
  label: string;
  score: number;
}

export interface Question {
  id: string;
  weight: number;
  prompt: string;
  dimension: string;
  options: QuestionOption[];
}

export interface Objective {
  id: string;
  label: string;
  description: string;
}

export interface RiskProfileResult {
  score: number;
  band: string;
  breakdown: { id: string; dimension: string; answer: string; score: number; weight: number }[];
  unanswered: string[];
  explanation: string;
}

export interface BacktestResult {
  startValue: number;
  endValue: number;
  invested: number;
  totalReturn: number;
  cagr: number;
  moneyWeightedReturn: number;
  annualizedReturn: number;
  volatility: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  maxDrawdown: number;
  recoveryPeriods: number | null;
  bestPeriod: number;
  worstPeriod: number;
  winningPeriods: number;
  losingPeriods: number;
  winRate: number;
  contributions: number;
  years: number;
  totalCosts?: number;
  totalTurnover?: number;
  rebalanceEvents?: number;
  bestYear?: { year: string; return: number } | null;
  worstYear?: { year: string; return: number } | null;
  calendarYears?: { year: string; return: number }[];
  equityCurve?: number[];
  performanceCurve?: number[];
  drawdownSeries?: number[];
  dates?: string[];
  weights?: Record<string, number>;
  finalWeights?: Record<string, number>;
  label?: string;
  /** Present on rebalancing comparisons. */
  frequency?: string;
}

export interface MonteCarloResponse {
  method: string;
  paths: number;
  years: number;
  seed: number | null;
  initialValue: number;
  periodicContribution: number;
  totalContributions: number;
  totalInvested: number;
  finalValues: Record<string, number>;
  medianFinalValue: number;
  meanFinalValue: number;
  probabilityOfLoss: number;
  probabilityOfDouble: number;
  percentilePaths: Record<string, number[]>;
  yearsAxis: number[];
  assumptions: Assumptions & { expectedAnnualReturn: number; annualVolatility: number };
  weights: Record<string, number>;
}

export interface StressScenario {
  key: string;
  name: string;
  description: string;
  shocks: { scope: string; target: string; shock: number }[];
  portfolioImpact: number;
  valueBefore: number;
  valueAfter: number;
  basis: string;
  caveat: string;
  assets: { symbol: string; weight: number; assetClass: string; shock: number; contribution: number; appliedBy: string }[];
}

export interface ApiError {
  error: string;
  code?: string;
  suggestions?: string[];
  detail?: Record<string, unknown>;
}
