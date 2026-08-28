import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const SECTIONS = [
  {
    title: "What this application is",
    body: [
      "This is a quantitative portfolio analysis and educational decision-support tool. It analyses historical market data, generates candidate allocations under constraints you set, and reports how those allocations behaved over the selected period.",
      "It is positioned deliberately as analysis and education, not as a personalised recommendation service.",
    ],
  },
  {
    title: "What this application is not",
    body: [
      "It is not a registered investment adviser, portfolio manager or broker. It does not provide personalised investment advice and does not take your full financial situation into account.",
      "It does not execute trades, hold assets, or contact any exchange or broker on your behalf.",
      "It does not provide tax, legal or accounting advice. Indian tax treatment depends on your residency, income slab and the specific instrument; consult a qualified professional.",
    ],
  },
  {
    title: "No guaranteed returns",
    body: [
      "Every figure labelled 'expected', 'model-estimated' or 'projected' is an estimate derived from historical data and explicit assumptions. None of it is a promise, a forecast, or a guaranteed outcome.",
      "Historical performance does not indicate future performance. Correlations, volatilities and drawdowns change over time, often when they are needed most.",
    ],
  },
  {
    title: "Model risk and assumptions",
    body: [
      "Optimisation finds allocations that scored best on a specific historical sample. That fit may not persist, and optimised portfolios are sensitive to small changes in inputs.",
      "Monte Carlo projections rely on assumed return distributions. Real markets produce moves that no model in this application captures.",
      "Backtests model transaction costs as a configurable assumption and do not model taxes, slippage, market impact or dividend treatment.",
      "Where data is missing, insufficient or inconsistent, the platform quarantines the affected asset and reports it rather than filling in values.",
    ],
  },
  {
    title: "Demo data",
    body: [
      "In Demo Data mode every price series is synthetic, generated from a seeded statistical model. It is clearly labelled throughout the interface and must never be treated as live or historical market data.",
      "When a live provider is configured but unavailable, the platform reports the failure or serves cached data with its timestamp. It never presents stale or synthetic data as live.",
    ],
  },
  {
    title: "Your responsibilities",
    body: [
      "Consider your full financial situation, liquidity needs, tax position and time horizon before acting on any output.",
      "Review the methodology page so you understand how each number is produced.",
      "Before offering anything derived from this software to clients commercially, obtain independent regulatory and legal review for your jurisdiction.",
    ],
  },
];

export default function DisclaimerPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <Badge tone="caution">Important</Badge>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">Disclaimer</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Please read this before relying on any output from this application.
        </p>
      </header>

      <Card className="border-amber-200 bg-amber-50/50">
        <CardBody>
          <p className="text-sm leading-relaxed text-amber-900">
            <strong className="font-semibold">Analytical tool only.</strong> Historical performance
            does not guarantee future performance. Expected returns are estimates, not promises.
            Correlations can change and model assumptions can fail. Nothing produced here is
            personalised, regulated investment advice.
          </p>
        </CardBody>
      </Card>

      {SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardHeader title={section.title} />
          <CardBody className="space-y-3">
            {section.body.map((paragraph) => (
              <p key={paragraph.slice(0, 40)} className="text-sm leading-relaxed text-ink-muted">
                {paragraph}
              </p>
            ))}
          </CardBody>
        </Card>
      ))}

      <Card>
        <CardBody className="text-xs leading-relaxed text-ink-subtle">
          Words this application deliberately avoids, in its own copy and in generated explanations:
          “guaranteed return”, “best investment”, “risk-free”, “sure-shot”, “will make money”.
          Where an output is uncertain, the interface says so.
        </CardBody>
      </Card>
    </div>
  );
}
