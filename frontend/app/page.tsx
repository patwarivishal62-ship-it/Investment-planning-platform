import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SHORT_DISCLAIMER } from "@/components/ui/Disclaimer";

const CAPABILITIES = [
  {
    title: "Six optimisation strategies",
    body: "Minimum variance, maximum Sharpe, return-under-risk, risk parity, maximum diversification and CVaR — solved subject to your constraints.",
  },
  {
    title: "Honest risk measurement",
    body: "Drawdown, downside deviation, historical VaR and CVaR, plus a transparent Platform Risk Score you can inspect component by component.",
  },
  {
    title: "Out-of-sample validation",
    body: "Walk-forward testing separates the period used to optimise from the period used to evaluate, so results are not fitted to the same data.",
  },
  {
    title: "Every number explained",
    body: "Each plan reports its return driver, its risk reducer, its concentration and its main risk — generated from the computed analytics.",
  },
];

const STEPS = [
  { step: "01", title: "Describe your goal", body: "Capital, contributions, horizon, objective and a short risk questionnaire." },
  { step: "02", title: "We search the space", body: "Tens of thousands of candidate allocations are generated, screened and scored." },
  { step: "03", title: "Compare five plans", body: "Five genuinely different portfolios, each with its own risk/return profile and rationale." },
];

export default function LandingPage() {
  return (
    <div className="space-y-20 pb-8">
      {/* ------------------------------------------------------------ hero */}
      <section className="grid items-center gap-10 pt-6 lg:grid-cols-[1.15fr_1fr] lg:pt-14">
        <div>
          <Badge tone="accent">Quantitative decision support</Badge>
          <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-[2.6rem]">
            Build a portfolio around your goals — not just around individual investments.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-ink-muted">
            Describe what you are investing for. The engine analyses historical behaviour across
            equities, fixed income, gold, silver, commodities and international assets, then ranks
            thousands of possible allocations and shows you the strongest five.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/onboarding">
              <Button size="lg">Build My Investment Plan</Button>
            </Link>
            <Link href="/analytics">
              <Button size="lg" variant="secondary">
                Explore the Analytics
              </Button>
            </Link>
          </div>
          <p className="mt-6 max-w-lg text-xs leading-relaxed text-ink-subtle">{SHORT_DISCLAIMER}</p>
        </div>

        <Card className="overflow-hidden">
          <div className="border-b border-line bg-stone-50 px-5 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              What you get
            </p>
          </div>
          <CardBody className="space-y-4">
            <HeroMetric label="Expected annualised return" value="11.42%" note="model-estimated, historical window" />
            <HeroMetric label="Annualised volatility" value="8.13%" note="annualised std. dev. of daily returns" />
            <HeroMetric label="Maximum drawdown" value="-10.8%" note="worst peak-to-trough, observed historically" />
            <HeroMetric label="Platform Risk Score" value="23/100" note="transparent, component-weighted" />
            <div className="border-t border-line pt-4">
              <p className="label mb-2">Illustrative allocation</p>
              <div className="flex h-2 w-full overflow-hidden rounded-full">
                {[
                  { width: "46%", color: "#4338CA" },
                  { width: "19%", color: "#0F766E" },
                  { width: "12%", color: "#B45309" },
                  { width: "18%", color: "#0E7490" },
                  { width: "5%", color: "#94A3B8" },
                ].map((bar, index) => (
                  <span key={index} style={{ width: bar.width, background: bar.color }} />
                ))}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.7rem] text-ink-subtle">
                <LegendDot color="#4338CA" label="Equity 46%" />
                <LegendDot color="#0F766E" label="Fixed income 19%" />
                <LegendDot color="#B45309" label="Gold 12%" />
                <LegendDot color="#0E7490" label="International 18%" />
                <LegendDot color="#94A3B8" label="Cash 5%" />
              </div>
            </div>
          </CardBody>
        </Card>
      </section>

      {/* ----------------------------------------------------------- steps */}
      <section>
        <h2 className="text-xl font-semibold tracking-tight text-ink">How it works</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {STEPS.map((item) => (
            <Card key={item.step} className="card-pad">
              <span className="num text-xs font-semibold text-accent-700">{item.step}</span>
              <h3 className="mt-2 text-sm font-semibold text-ink">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{item.body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* --------------------------------------------------- capabilities */}
      <section>
        <h2 className="text-xl font-semibold tracking-tight text-ink">
          Built as an analytical engine, not a dashboard
        </h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {CAPABILITIES.map((item) => (
            <Card key={item.title} className="card-pad">
              <h3 className="text-sm font-semibold text-ink">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{item.body}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------ data note */}
      <section>
        <Card className="card-pad">
          <h2 className="text-sm font-semibold text-ink">About the data</h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-muted">
            The application ships in <strong className="font-medium text-ink">Demo Data</strong>{" "}
            mode: a deterministic synthetic market generated from a seeded factor model. It is
            clearly labelled everywhere and is never presented as live or historical market data.
            Configure a provider in Settings to switch to live data — the analytics, optimiser and
            every page work identically against either source.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link href="/onboarding">
              <Button size="sm">Explore with Demo Data</Button>
            </Link>
            <Link href="/methodology">
              <Button size="sm" variant="secondary">Read the methodology</Button>
            </Link>
          </div>
        </Card>
      </section>
    </div>
  );
}

function HeroMetric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line pb-3 last:border-0 last:pb-0">
      <div>
        <p className="text-sm text-ink">{label}</p>
        <p className="text-[0.7rem] text-ink-subtle">{note}</p>
      </div>
      <p className="num shrink-0 text-lg font-semibold text-ink">{value}</p>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className="h-2 w-2 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}
