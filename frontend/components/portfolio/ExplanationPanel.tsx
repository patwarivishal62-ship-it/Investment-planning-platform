"use client";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { formatPercent } from "@/lib/format";
import type { PlanExplanation } from "@/types";

/**
 * Renders the engine's explanation. Every sentence was assembled server-side
 * from computed analytics -- nothing here invents a number.
 */
export function ExplanationPanel({ explanation }: { explanation: PlanExplanation }) {
  return (
    <Card>
      <CardHeader title="Why this portfolio?" subtitle={explanation.summary} />
      <CardBody className="space-y-5">
        <Section title="Return driver" body={explanation.returnDriver.text}>
          <ul className="mt-2 space-y-1">
            {explanation.returnDriver.assets.map((asset) => (
              <li key={asset.symbol} className="flex justify-between gap-3 text-xs text-ink-muted">
                <span className="truncate">{asset.name}</span>
                <span className="num shrink-0">
                  {formatPercent(asset.shareOfReturn, 0)} of expected return
                </span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Risk reducer" body={explanation.riskReducer.text}>
          <ul className="mt-2 space-y-1">
            {explanation.riskReducer.assets.map((asset) => (
              <li key={asset.symbol} className="flex justify-between gap-3 text-xs text-ink-muted">
                <span className="truncate">{asset.name}</span>
                <span className="num shrink-0">
                  corr {asset.correlationToPortfolio.toFixed(2)} · risk share{" "}
                  {formatPercent(asset.riskShare, 0)}
                </span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Diversification" body={explanation.diversification.text} />

        <Section title="Main risk" body={explanation.mainRisk.text}>
          <ul className="mt-2 space-y-1">
            {explanation.mainRisk.assets.map((asset) => (
              <li key={asset.symbol} className="flex justify-between gap-3 text-xs text-ink-muted">
                <span className="truncate">{asset.name}</span>
                <span className="num shrink-0">
                  {formatPercent(asset.riskShare, 0)} of portfolio risk
                </span>
              </li>
            ))}
          </ul>
        </Section>

        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
          <p className="text-xs font-semibold text-amber-900">Important caveat</p>
          <p className="mt-1 text-xs leading-relaxed text-amber-900">{explanation.caveat}</p>
        </div>
      </CardBody>
    </Card>
  );
}

function Section({
  title,
  body,
  children,
}: {
  title: string;
  body: string;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-ink-muted">{body}</p>
      {children}
    </div>
  );
}
