"use client";

import { formatNumber, formatPercent, formatScore } from "@/lib/format";
import type { RiskScore } from "@/types";

const INPUT_LABELS: Record<string, string> = {
  volatility: "Annualised volatility",
  maxDrawdown: "Maximum drawdown",
  downsideDeviation: "Downside deviation",
  dailyVaR: "Daily VaR (95%)",
  equityExposure: "Equity exposure",
  effectiveAssets: "Effective positions",
  weightedLiquidity: "Weighted liquidity",
};

/**
 * Shows exactly how the Platform Risk Score was produced (spec section 26):
 * every input, its weight in the composite and its contribution to the score.
 */
export function RiskScoreBreakdown({ riskScore }: { riskScore: RiskScore }) {
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="label">Platform Risk Score</p>
          <p className="num text-2xl font-semibold text-ink">{formatScore(riskScore.score)}</p>
        </div>
        <p className="text-sm text-ink-muted">{riskScore.band}</p>
      </div>

      <div className="overflow-hidden rounded-lg border border-line">
        <table className="w-full text-sm">
          <caption className="sr-only">
            Components of the Platform Risk Score with their weights and contributions
          </caption>
          <thead className="bg-stone-50 text-left text-xs text-ink-muted">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Component</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Weight</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Normalised</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Points</th>
            </tr>
          </thead>
          <tbody>
            {riskScore.components.map((component) => (
              <tr key={component.key} className="border-t border-line">
                <td className="px-3 py-2 text-ink">{humanise(component.key)}</td>
                <td className="num px-3 py-2 text-right text-ink-muted">
                  {formatPercent(component.weight, 0)}
                </td>
                <td className="num px-3 py-2 text-right text-ink-muted">
                  {formatNumber(component.normalized, 2)}
                </td>
                <td className="num px-3 py-2 text-right font-medium text-ink">
                  {formatNumber(component.contribution, 1)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line bg-stone-50">
              <td className="px-3 py-2 font-medium text-ink">Total</td>
              <td colSpan={2} />
              <td className="num px-3 py-2 text-right font-semibold text-ink">
                {formatNumber(riskScore.score, 1)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div>
        <p className="label mb-2">Inputs used</p>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-3">
          {Object.entries(riskScore.inputs).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-2">
              <dt className="truncate text-ink-subtle">{INPUT_LABELS[key] ?? humanise(key)}</dt>
              <dd className="num shrink-0 font-medium text-ink">
                {key === "effectiveAssets" ? formatNumber(value, 1) : formatPercent(value, 1)}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <p className="text-xs leading-relaxed text-ink-subtle">
        This is a platform-defined composite score, not an industry-standard or regulated risk
        measure. It describes how the portfolio behaved over the selected period under the stated
        assumptions; it does not predict future risk.
      </p>
    </div>
  );
}

function humanise(key: string) {
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (character) => character.toUpperCase())
    .replace("Value At Risk", "VaR");
}
