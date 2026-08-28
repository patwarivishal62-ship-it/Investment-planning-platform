"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ErrorState, ProgressNote, Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { PlanCard } from "@/components/portfolio/PlanCard";
import { AssumptionBar } from "@/components/portfolio/AssumptionBar";
import { api, ApiRequestError } from "@/lib/api";
import { buildRecommendPayload, useApp } from "@/lib/store";
import { useAssets } from "@/lib/hooks/useAssets";
import { formatINR, formatPercent } from "@/lib/format";
import type { Plan } from "@/types";

function RecommendationsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { profile, constraints, universe, plans, setPlans, recommendations, compare, toggleCompare, hydrated } = useApp();
  const { classOf } = useAssets();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const requested = useRef(false);

  const generate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setProgress("Generating candidate portfolios…");
    try {
      const payload = buildRecommendPayload(profile, constraints, universe);
      const result = await api.recommend(payload);
      setPlans(result.plans, result);
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? err
          : new ApiRequestError("Unable to generate plans.", 0),
      );
    } finally {
      setLoading(false);
      setProgress(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, constraints, universe]);

  useEffect(() => {
    if (!hydrated || requested.current) return;
    if (params.get("generate") === "1" || plans.length === 0) {
      requested.current = true;
      void generate();
    }
  }, [hydrated, params, plans.length, generate]);

  const bestFit = plans.find((plan) => plan.bestFit);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Your Investment Plans</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Based on your objectives, risk profile and the selected historical data.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/onboarding">
            <Button variant="secondary" size="sm">Edit profile</Button>
          </Link>
          <Button size="sm" onClick={generate} disabled={loading}>
            {loading ? <Spinner /> : null} Regenerate
          </Button>
        </div>
      </header>

      <Card>
        <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Summary label="Initial capital" value={formatINR(profile.initialInvestment, { compact: true })} />
          <Summary
            label="Monthly contribution"
            value={formatINR(profile.monthlyContribution, { compact: true })}
          />
          <Summary label="Horizon" value={`${profile.horizonYears} years`} />
          <Summary
            label="Risk profile"
            value={`${profile.riskBand} (${Math.round(profile.riskScore)}/100)`}
          />
        </CardBody>
      </Card>

      {loading ? (
        <ProgressNote>
          {progress ?? "Analysing portfolios…"} This typically takes a couple of seconds.
        </ProgressNote>
      ) : null}

      {error ? (
        <ErrorState
          title={error.code === "no_feasible_portfolio" ? "No portfolio satisfies your constraints" : "Generation failed"}
          message={error.message}
          suggestions={error.suggestions}
          onRetry={generate}
        />
      ) : null}

      {!loading && plans.length > 0 ? (
        <>
          <AssumptionBar assumptions={recommendations?.assumptions} />

          {bestFit ? (
            <Card className="border-accent-200 bg-accent-50/40">
              <CardBody>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge tone="accent">Best Fit</Badge>
                      <h2 className="text-base font-semibold text-ink">{bestFit.name}</h2>
                    </div>
                    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
                      This portfolio scored highest against your selected objectives and risk
                      constraints — not because it is the &ldquo;best&rdquo; portfolio outright, but
                      because it fits the profile you described.{" "}
                      {bestFit.explanation.summary}
                    </p>
                  </div>
                  <Link href={`/portfolio/${bestFit.id}`}>
                    <Button size="sm">See why</Button>
                  </Link>
                </div>
              </CardBody>
            </Card>
          ) : null}

          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold tracking-tight text-ink">
                {plans.length} plans, {plans.length > 1 ? "each built differently" : ""}
              </h2>
              {compare.length ? (
                <Link href="/compare">
                  <Button size="sm" variant="secondary">Compare {compare.length} selected</Button>
                </Link>
              ) : (
                <span className="text-xs text-ink-subtle">
                  Select up to five plans with “Compare” to see them side by side.
                </span>
              )}
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {plans.map((plan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  classOf={classOf}
                  comparing={compare.includes(plan.id)}
                  onCompare={toggleCompare}
                />
              ))}
            </div>
          </div>

          {recommendations ? (
            <Card>
              <CardHeader
                title="How these were selected"
                subtitle="Every plan is produced by the optimiser; the scoring weights are configurable."
              />
              <CardBody className="space-y-3 text-sm">
                <p className="text-ink-muted">
                  {recommendations.candidateCount.toLocaleString("en-IN")} candidate allocations were
                  generated and screened; {recommendations.evaluatedCount.toLocaleString("en-IN")} were
                  scored on the full set of metrics. Plans are then picked one per risk band with a
                  diversity penalty, so you are not shown five versions of the same portfolio.
                </p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(recommendations.scoringWeights).map(([key, weight]) => (
                    <Badge key={key} tone="neutral">
                      {key.replace(/([A-Z])/g, " $1")} {formatPercent(weight, 0)}
                    </Badge>
                  ))}
                </div>
              </CardBody>
            </Card>
          ) : null}
        </>
      ) : null}

      {!loading && !error && plans.length === 0 ? (
        <Card>
          <CardBody className="py-10 text-center">
            <p className="text-sm text-ink-muted">No plans yet.</p>
            <Button className="mt-4" onClick={generate}>Generate plans</Button>
          </CardBody>
        </Card>
      ) : null}

      <Disclaimer>
        Plans are optimised against historical data and are illustrative model output. Expected
        returns are estimates, not promises, and historical relationships may change. Not
        investment advice.
      </Disclaimer>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="num mt-1 text-lg font-semibold text-ink">{value}</p>
    </div>
  );
}

/**
 * useSearchParams needs a Suspense boundary for static generation, so the page
 * shell wraps the data-driven content.
 */
export default function RecommendationsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center gap-2 py-16 text-sm text-ink-muted">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-stone-300 border-t-accent-700" />
          Loading plans…
        </div>
      }
    >
      <RecommendationsContent />
    </Suspense>
  );
}
