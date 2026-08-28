/**
 * Runtime contract check.
 *
 * Replays every API call the frontend makes, with the exact payload shapes the
 * pages build, and asserts that every field the components read is present.
 * This catches "the page renders but shows undefined" class of bug without a
 * browser.
 *
 * Usage: node scripts/contract-check.mjs [baseUrl]
 */
const BASE = process.argv[2] || "http://127.0.0.1:3000/api";

let failures = 0;
let checks = 0;

function has(label, obj, path) {
  checks++;
  const value = path.split(".").reduce((acc, key) => (acc == null ? acc : acc[key]), obj);
  if (value === undefined || value === null) {
    failures++;
    console.log(`  ✗ ${label}: missing ${path}`);
    return undefined;
  }
  return value;
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${path} → ${res.status} ${JSON.stringify(await res.json()).slice(0, 300)}`);
  }
  return res.json();
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

// A realistic profile: ₹10,00,000 + ₹20,000/month, 10 years, moderate risk.
const PROFILE = { riskScore: 55, objective: "wealth_creation" };
const SYMBOLS = [
  "NIFTY50", "NIFTYNEXT50", "NIFTYBANK", "NIFTYIT", "NIFTYPHARMA",
  "GOLD", "SILVER", "GSEC10Y", "CORPBOND", "LIQUIDFUND",
  "GLOBAL_ETF", "IND_REIT", "CRUDE",
];
const WEIGHTS = Object.fromEntries(SYMBOLS.map((s) => [s, 1 / SYMBOLS.length]));

async function main() {
  console.log(`Contract check against ${BASE}\n`);

  // ----------------------------------------------------------- shared data
  console.log("System & assets");
  const status = await get("/data/status");
  has("status", status, "mode");
  has("status", status, "provider");
  has("status", status, "lastUpdated");
  has("status", status, "assetCount");
  has("status", status, "historyStart");
  has("status", status, "historyEnd");
  has("status", status, "dataQuality.score");
  has("status", status, "dataQuality.grade");

  const config = await get("/config");
  has("config", config, "riskFreeRate");
  has("config", config, "tradingDaysPerYear");

  const assets = await get("/assets");
  has("assets", assets[0], "symbol");
  has("assets", assets[0], "name");
  has("assets", assets[0], "assetClass");
  has("assets", assets[0], "currency");

  const questions = await get("/profile/questions");
  if (!Array.isArray(questions) && !questions.questions) throw new Error("questions shape unexpected");
  checks++;

  // --------------------------------------------------------- risk scoring
  console.log("Risk profile");
  const answers = {
    horizon: "long",
    drawdown_reaction: "hold",
    experience: "some",
    income_stability: "stable",
    liquidity_need: "low",
    objective_clarity: "clear",
  };
  let profileResult;
  try {
    profileResult = await post("/profile/risk-score", { answers });
    has("riskScore", profileResult, "score");
    has("riskScore", profileResult, "band");
  } catch (err) {
    // Answer ids may differ; fall back to the first option of every question.
    const list = Array.isArray(questions) ? questions : questions.questions;
    const fallback = {};
    for (const q of list) fallback[q.id] = q.options[0].id ?? q.options[0].value;
    profileResult = await post("/profile/risk-score", { answers: fallback });
    has("riskScore", profileResult, "score");
    has("riskScore", profileResult, "band");
  }

  // ------------------------------------------------------- analytics page
  console.log("Analytics workspace");
  const analytics = await post("/analytics/assets", { symbols: SYMBOLS });
  has("analytics", analytics, "period.start");
  has("analytics", analytics, "period.end");
  has("analytics", analytics, "assets.0.symbol");
  has("analytics", analytics, "assets.0.annualizedReturn");
  has("analytics", analytics, "assets.0.cagr");
  has("analytics", analytics, "assets.0.volatility");
  has("analytics", analytics, "assets.0.sharpe");
  has("analytics", analytics, "assets.0.sortino");
  has("analytics", analytics, "assets.0.calmar");
  has("analytics", analytics, "assets.0.maxDrawdown");
  has("analytics", analytics, "assets.0.bestPeriod");
  has("analytics", analytics, "assets.0.worstPeriod");
  has("analytics", analytics, "assets.0.downsideDeviation");
  has("analytics", analytics, "assets.0.historicalCVaR");
  has("analytics", analytics, "dataQuality.score");
  has("analytics", analytics, "correlation.symbols");
  has("analytics", analytics, "correlation.matrix");
  has("analytics", analytics, "correlation.averagePairwiseCorrelation");

  const corr = await post("/analytics/correlation", { symbols: SYMBOLS, window: 252 });
  has("correlation", corr, "symbols");
  has("correlation", corr, "matrix");
  has("correlation", corr, "averagePairwiseCorrelation");

  const advanced = await post("/portfolio/advanced", {
    weights: WEIGHTS, symbols: SYMBOLS, benchmark: "NIFTY50",
  });
  has("advanced", advanced, "distribution.bins");
  has("advanced", advanced, "distribution.counts");
  has("advanced", advanced, "distribution.statistics");
  has("advanced", advanced, "rollingVolatility");
  has("advanced", advanced, "rollingReturn");
  has("advanced", advanced, "betaAlpha.beta");
  has("advanced", advanced, "betaAlpha.alpha");
  has("advanced", advanced, "betaAlpha.rSquared");
  has("advanced", advanced, "trackingError");
  has("advanced", advanced, "informationRatio");
  has("advanced", advanced, "captureRatios.upsideCapture");
  has("advanced", advanced, "captureRatios.downsideCapture");

  const frontier = await post("/efficient-frontier", { symbols: SYMBOLS, points: 45 });
  has("frontier", frontier, "points.0.volatility");
  has("frontier", frontier, "points.0.expectedReturn");
  has("frontier", frontier, "minVariance.volatility");
  has("frontier", frontier, "tangency.volatility");
  has("frontier", frontier, "riskFreeRate");

  // -------------------------------------------------------- recommendations
  console.log("Recommendations (the core journey)");
  const rec = await post("/portfolio/recommend", {
    capital: 1_000_000,
    monthlyContribution: 20_000,
    horizonYears: 10,
    riskScore: PROFILE.riskScore,
    objective: PROFILE.objective,
    rebalanceFrequency: "quarterly",
  });
  has("recommend", rec, "plans");
  has("recommend", rec, "candidateCount");
  has("recommend", rec, "evaluatedCount");
  has("recommend", rec, "scoringWeights");
  has("recommend", rec, "assumptions.riskFreeRate");
  if (rec.plans.length < 4) {
    failures++;
    console.log(`  ✗ only ${rec.plans.length} plans returned (expected 4-5)`);
  }
  checks++;

  rec.plans.forEach((plan, index) => {
    const label = `plan[${index}] ${plan.name}`;
    has(label, plan, "id");
    has(label, plan, "name");
    has(label, plan, "summary");
    has(label, plan, "score");
    has(label, plan, "fitScore");
    has(label, plan, "subScores");
    has(label, plan, "explanation.summary");
    has(label, plan, "explanation.caveat");
    has(label, plan, "explanation.returnDriver.text");
    has(label, plan, "explanation.riskReducer.text");
    has(label, plan, "explanation.diversification.text");
    has(label, plan, "explanation.mainRisk.text");
    const m = plan.metrics;
    for (const key of [
      "weights", "expectedReturn", "cagr", "volatility", "sharpe", "sortino",
      "calmar", "maxDrawdown", "downsideDeviation", "ulcerIndex",
      "historicalVaR", "historicalCVaR", "diversificationRatio",
      "effectiveAssets", "assetClassExposure", "weightedLiquidity",
      "riskContribution", "returnContribution", "equityCurve", "dates",
      "drawdownSeries", "drawdowns",
    ]) {
      has(label, m, key);
    }
    has(label, m, "riskScore.score");
    has(label, m, "riskScore.band");
    has(label, m, "riskScore.components");
    has(label, m, "riskScore.inputs");
    // Weights must sum to 1 and be non-negative for every plan shown.
    const sum = Object.values(m.weights).reduce((a, b) => a + b, 0);
    checks++;
    if (Math.abs(sum - 1) > 1e-6) {
      failures++;
      console.log(`  ✗ ${label}: weights sum to ${sum}`);
    }
    const negative = Object.entries(m.weights).filter(([, w]) => w < -1e-9);
    if (negative.length) {
      failures++;
      console.log(`  ✗ ${label}: negative weights ${JSON.stringify(negative)}`);
    }
    checks++;
  });

  // Plans must be genuinely different from one another.
  for (let i = 0; i < rec.plans.length; i++) {
    for (let j = i + 1; j < rec.plans.length; j++) {
      const a = rec.plans[i].metrics.weights;
      const b = rec.plans[j].metrics.weights;
      const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
      const l1 = [...keys].reduce((acc, k) => acc + Math.abs((a[k] || 0) - (b[k] || 0)), 0);
      checks++;
      if (l1 < 0.3) {
        failures++;
        console.log(`  ✗ plans ${i}/${j} are near-identical (L1 = ${l1.toFixed(3)})`);
      }
    }
  }

  const best = rec.plans.filter((p) => p.bestFit);
  checks++;
  if (best.length !== 1) {
    failures++;
    console.log(`  ✗ expected exactly one bestFit plan, got ${best.length}`);
  }

  console.log("\nPlan summary");
  for (const plan of rec.plans) {
    const m = plan.metrics;
    console.log(
      `  ${plan.name.padEnd(22)} ret ${(m.expectedReturn * 100).toFixed(2).padStart(6)}%  ` +
      `vol ${(m.volatility * 100).toFixed(2).padStart(5)}%  sharpe ${m.sharpe.toFixed(2)}  ` +
      `maxDD ${(m.maxDrawdown * 100).toFixed(2).padStart(6)}%  risk ${String(m.riskScore.score).padStart(3)}  ` +
      `fit ${plan.fitScore.toFixed(3)}${plan.bestFit ? "  ★" : ""}`,
    );
  }

  const bestPlan = best[0] ?? rec.plans[0];
  const bestWeights = bestPlan.metrics.weights;
  const bestSymbols = Object.keys(bestWeights);

  // ---------------------------------------------------------- portfolio detail
  console.log("\nPortfolio detail tabs");
  const analyze = await post("/portfolio/analyze", { weights: bestWeights, symbols: bestSymbols });
  has("analyze", analyze, "weights");
  has("analyze", analyze, "volatility");

  const whatIf = await post("/portfolio/what-if", {
    weights: bestWeights,
    symbols: bestSymbols,
    // Move 10% from the largest holding into cash.
    changes: { [bestSymbols[0]]: (bestWeights[bestSymbols[0]] ?? 0) - 0.1 },
  });
  has("whatIf", whatIf, "metrics.volatility");
  has("whatIf", whatIf, "metrics.expectedReturn");
  has("whatIf", whatIf, "assumptions");

  const riskContrib = await post("/portfolio/risk-contribution", {
    weights: bestWeights, symbols: bestSymbols,
  });
  has("riskContribution", riskContrib, "contributions");
  has("riskContribution", riskContrib, "portfolioVolatility");
  has("riskContribution", riskContrib, "contributions.0.riskShare");

  const diversification = await post("/portfolio/diversification", {
    weights: bestWeights, symbols: bestSymbols,
  });
  // Diversification is returned as a before/after step ladder.
  has("diversification", diversification, "steps.0.metrics.diversificationRatio");
  has("diversification", diversification, "steps.0.metrics.effectiveAssets");
  has("diversification", diversification, "steps.0.label");

  // ------------------------------------------------------------------ optimizer
  console.log("Optimizer");
  for (const strategy of [
    "min_variance", "max_sharpe", "risk_parity",
    "max_diversification", "max_return_for_risk", "min_cvar",
  ]) {
    const opt = await post("/portfolio/optimize", {
      symbols: SYMBOLS,
      strategies: [strategy],
      maxWeight: 0.4,
      maxVolatility: 0.18,
      targetVolatility: strategy === "max_return_for_risk" ? 0.18 : undefined,
    });
    has(`optimize:${strategy}`, opt, "results.0.metrics.weights");
    has(`optimize:${strategy}`, opt, "results.0.metrics.volatility");
    has(`optimize:${strategy}`, opt, "assumptions");
  }
  const bounded = await post("/portfolio/optimize", {
    symbols: SYMBOLS,
    strategies: ["max_sharpe"],
    maxWeight: 0.25,
    classBounds: { equity: [0, 0.3] },
  });
  const bw = bounded.results[0].metrics.weights;
  const equityMap = Object.fromEntries(assets.map((a) => [a.symbol, a.assetClass]));
  const equity = Object.entries(bw).reduce(
    (acc, [sym, w]) => acc + (equityMap[sym] === "equity" ? w : 0), 0,
  );
  checks++;
  if (equity > 0.3 + 1e-6) {
    failures++;
    console.log(`  ✗ equity class bound breached: ${equity.toFixed(4)} > 0.30`);
  }

  // Infeasible constraints must not fabricate a portfolio.
  let rejected = false;
  try {
    const r = await fetch(`${BASE}/portfolio/optimize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols: SYMBOLS, strategies: ["max_sharpe"], maxVolatility: 0.0001 }),
    });
    const body = await r.json();
    checks++;
    if (r.status === 200 || r.status === 201) {
      failures++;
      console.log("  ✗ infeasible request returned 200 instead of an error");
    } else if (!body.code || !Array.isArray(body.suggestions)) {
      failures++;
      console.log(`  ✗ infeasible error missing code/suggestions: ${JSON.stringify(body).slice(0, 200)}`);
    } else {
      rejected = true;
    }
  } catch {
    failures++;
    console.log("  ✗ infeasible request threw");
  }
  console.log(`  infeasible constraints rejected with guidance: ${rejected ? "yes" : "NO"}`);

  // ------------------------------------------------------------------- backtest
  console.log("Backtest");
  const bt = await post("/backtest", {
    weights: bestWeights, symbols: bestSymbols,
    initialValue: 1_000_000, monthlyContribution: 20_000,
    rebalanceFrequency: "quarterly", transactionCostBps: 10,
  });
  has("backtest", bt, "portfolio.cagr");
  has("backtest", bt, "portfolio.totalReturn");
  has("backtest", bt, "portfolio.maxDrawdown");
  has("backtest", bt, "portfolio.volatility");
  has("backtest", bt, "portfolio.sharpe");
  has("backtest", bt, "portfolio.sortino");
  has("backtest", bt, "portfolio.endValue");
  has("backtest", bt, "portfolio.invested");
  has("backtest", bt, "portfolio.moneyWeightedReturn");
  has("backtest", bt, "portfolio.equityCurve");
  has("backtest", bt, "portfolio.performanceCurve");
  has("backtest", bt, "portfolio.drawdownSeries");
  has("backtest", bt, "portfolio.dates");
  has("backtest", bt, "portfolio.winningPeriods");
  has("backtest", bt, "portfolio.losingPeriods");
  has("backtest", bt, "portfolio.winRate");
  has("backtest", bt, "portfolio.calendarYears");
  has("backtest", bt, "portfolio.totalCosts");
  has("backtest", bt, "portfolio.rebalanceEvents");
  has("backtest", bt, "benchmarks.0.symbol");
  has("backtest", bt, "benchmarks.0.cagr");

  // The critical regression: contributions must not be counted as performance.
  checks++;
  if (bt.portfolio.cagr > 0.30) {
    failures++;
    console.log(`  ✗ CAGR ${(bt.portfolio.cagr * 100).toFixed(2)}% looks contribution-inflated`);
  }
  console.log(
    `  time-weighted CAGR ${(bt.portfolio.cagr * 100).toFixed(2)}% vs money-weighted ` +
    `${(bt.portfolio.moneyWeightedReturn * 100).toFixed(2)}%  ` +
    `(invested ${bt.portfolio.invested.toLocaleString("en-IN")} → ${bt.portfolio.endValue.toLocaleString("en-IN")})`,
  );

  const reb = await post("/backtest/rebalance", {
    weights: bestWeights, symbols: bestSymbols,
    initialValue: 1_000_000, monthlyContribution: 20_000, transactionCostBps: 10,
  });
  has("rebalance", reb, "results.0.frequency");
  has("rebalance", reb, "results.0.cagr");
  has("rebalance", reb, "results.0.endValue");

  const wf = await post("/backtest/walk-forward", {
    symbols: bestSymbols, trainEnd: "2023-12-31", strategy: "max_sharpe",
    initialValue: 1_000_000, monthlyContribution: 20_000,
    rebalanceFrequency: "quarterly", transactionCostBps: 10,
  });
  has("walkForward", wf, "inSample.cagr");
  has("walkForward", wf, "outOfSample.cagr");
  has("walkForward", wf, "outOfSample.dates");
  has("walkForward", wf, "outOfSample.performanceCurve");
  has("walkForward", wf, "assumptions.trainEnd");
  has("walkForward", wf, "assumptions.testStart");
  checks++;
  if (!(wf.assumptions.testStart > wf.assumptions.trainEnd)) {
    failures++;
    console.log("  ✗ walk-forward test window does not start after training ends");
  }
  console.log(
    `  in-sample ${(wf.inSample.cagr * 100).toFixed(2)}% → out-of-sample ` +
    `${(wf.outOfSample.cagr * 100).toFixed(2)}%`,
  );
  if (wf.benchmarkOutOfSample) {
    const bench = wf.benchmarkOutOfSample;
    console.log(
      `  same window, buy-and-hold ${bench.symbol}: ${(bench.cagr * 100).toFixed(2)}% ` +
      `(sanity check that the OOS gap is the regime, not a look-ahead bug)`,
    );
  }

  // --------------------------------------------------------------- monte carlo
  console.log("Monte Carlo");
  const mc1 = await post("/monte-carlo", {
    weights: bestWeights, symbols: bestSymbols,
    initialValue: 1_000_000, monthlyContribution: 20_000,
    annualContributionIncrease: 0.05, years: 10, paths: 2000, method: "normal", seed: 42,
  });
  for (const key of [
    "yearsAxis", "percentilePaths", "finalValues.p10", "finalValues.p25",
    "finalValues.p50", "finalValues.p75", "finalValues.p90",
    "probabilityOfLoss", "probabilityOfDouble", "totalInvested",
    "initialValue", "years", "paths", "method",
    "assumptions.expectedAnnualReturn", "assumptions.annualVolatility",
  ]) {
    has("monteCarlo", mc1, key);
  }
  const mc2 = await post("/monte-carlo", {
    weights: bestWeights, symbols: bestSymbols,
    initialValue: 1_000_000, monthlyContribution: 20_000,
    annualContributionIncrease: 0.05, years: 10, paths: 2000, method: "normal", seed: 42,
  });
  checks++;
  if (mc1.finalValues.p50 !== mc2.finalValues.p50) {
    failures++;
    console.log("  ✗ same seed produced different results (not deterministic)");
  }
  console.log(`  P10 ${mc1.finalValues.p10.toLocaleString("en-IN")} · P50 ` +
    `${mc1.finalValues.p50.toLocaleString("en-IN")} · P90 ${mc1.finalValues.p90.toLocaleString("en-IN")} ` +
    `· reproducible: ${mc1.finalValues.p50 === mc2.finalValues.p50 ? "yes" : "NO"}`);

  // ------------------------------------------------------------- stress test
  console.log("Stress test");
  const st = await post("/stress-test", {
    weights: bestWeights, symbols: bestSymbols, portfolioValue: 1_000_000,
  });
  has("stress", st, "scenarios.0.key");
  has("stress", st, "scenarios.0.name");
  has("stress", st, "scenarios.0.portfolioImpact");
  has("stress", st, "scenarios.0.valueBefore");
  has("stress", st, "scenarios.0.valueAfter");
  has("stress", st, "scenarios.0.assets.0.contribution");
  for (const scenario of st.scenarios) {
    console.log(`  ${scenario.name.padEnd(24)} ${(scenario.portfolioImpact * 100).toFixed(2).padStart(7)}%`);
  }
  const custom = await post("/stress-test", {
    weights: bestWeights, symbols: bestSymbols, portfolioValue: 1_000_000,
    scenarios: ["custom"],
    customShocks: [{ scope: "assetClass", target: "equity", shock: -0.3 }],
  });
  const customScenario = custom.scenarios.find((s) => s.key === "custom");
  checks++;
  if (!customScenario) {
    failures++;
    console.log("  ✗ custom scenario not returned");
  } else {
    console.log(`  custom equity −30% shock → ${(customScenario.portfolioImpact * 100).toFixed(2)}%`);
  }

  // -------------------------------------------------------------------- result
  console.log(`\n${failures ? "✗" : "✓"} ${checks - failures}/${checks} contract checks passed`);
  process.exit(failures ? 1 : 0);
}

main().catch((err) => {
  console.error("\nFatal:", err.message);
  process.exit(1);
});
