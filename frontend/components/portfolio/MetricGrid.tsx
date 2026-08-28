"use client";

import { Stat } from "@/components/ui/Stat";
import { formatNumber, formatPercent, formatScore, riskBandTone } from "@/lib/format";
import type { PortfolioMetrics } from "@/types";
import { cn } from "@/lib/utils";

/** The headline metric cards (spec section 28). Hints link to the methodology. */
export function MetricGrid({
  metrics,
  columns = 4,
  showRiskScore = true,
  compact = false,
}: {
  metrics: PortfolioMetrics;
  columns?: 3 | 4;
  showRiskScore?: boolean;
  compact?: boolean;
}) {
  const gridCols = compact
    ? "grid-cols-2 sm:grid-cols-3"
    : columns === 3
      ? "grid-cols-2 sm:grid-cols-3"
      : "grid-cols-2 sm:grid-cols-4";

  return (
    <div className={cn("grid gap-x-6 gap-y-5", gridCols)}>
      <Stat
        label="Expected return"
        value={formatPercent(metrics.expectedReturn)}
        sub="annualised, arithmetic"
        hint="Arithmetic annualised mean of the portfolio's daily returns over the selected period."
      />
      <Stat
        label="Volatility"
        value={formatPercent(metrics.volatility)}
        sub="annualised std. dev."
        hint="Standard deviation of daily returns scaled by the square root of trading days per year."
      />
      <Stat
        label="Sharpe"
        value={formatNumber(metrics.sharpe)}
        sub="excess return / volatility"
        hint="(Expected return − risk-free rate) ÷ volatility. Higher means more return per unit of risk."
      />
      <Stat
        label="Sortino"
        value={formatNumber(metrics.sortino)}
        sub="excess / downside dev."
        hint="Like Sharpe, but only penalises returns below the minimum acceptable return."
      />
      <Stat
        label="Max drawdown"
        value={formatPercent(metrics.maxDrawdown)}
        tone={metrics.maxDrawdown < -0.25 ? "negative" : "default"}
        sub="worst peak-to-trough"
        hint="The largest observed fall from a previous high during the selected period."
      />
      <Stat
        label="VaR (95%)"
        value={formatPercent(metrics.historicalVaR)}
        sub="1-day historical"
        hint="Historical Value at Risk: the loss level exceeded on the worst 5% of days."
      />
      <Stat
        label="CVaR (95%)"
        value={formatPercent(metrics.historicalCVaR)}
        sub="expected shortfall"
        hint="Average loss on the worst 5% of days — the tail beyond VaR."
      />
      {showRiskScore ? (
        <div>
          <Stat
            label="Platform Risk Score"
            value={formatScore(metrics.riskScore?.score)}
            sub={metrics.riskScore?.band}
            hint="A transparent composite of volatility, drawdown, downside risk, VaR, equity exposure, concentration and liquidity. Not an industry-standard measure."
          />
          {metrics.riskScore ? (
            <span
              className={cn(
                "mt-1.5 inline-block rounded-md border px-2 py-0.5 text-[0.7rem] font-medium",
                riskBandTone(metrics.riskScore.band),
              )}
            >
              {metrics.riskScore.band}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
