"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Field, RadioGroup, Select, TextInput } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Feedback";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { formatINR, formatPercent, riskBandTone } from "@/lib/format";
import type { Asset, Question } from "@/types";
import { cn } from "@/lib/utils";

const STEPS = ["Capital", "Horizon", "Objective", "Risk", "Universe"];

export default function OnboardingPage() {
  const router = useRouter();
  const { profile, setProfile, universe, setUniverse } = useApp();
  const [step, setStep] = useState(0);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [objectives, setObjectives] = useState<{ id: string; label: string; description: string }[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>(profile.answers ?? {});
  const [riskResult, setRiskResult] = useState<{ score: number; band: string; explanation: string } | null>(
    profile.answers && Object.keys(profile.answers).length
      ? { score: profile.riskScore, band: profile.riskBand, explanation: "" }
      : null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.questions().then((payload) => {
      setQuestions(payload.questions);
      setObjectives(payload.objectives);
    }).catch(() => undefined);
    api.assets().then(setAssets).catch(() => undefined);
  }, []);

  const answeredCount = Object.keys(answers).length;
  const canAdvance =
    step === 0 ? profile.initialInvestment >= 0
      : step === 1 ? profile.horizonYears > 0
        : step === 2 ? Boolean(profile.objective)
          : step === 3 ? answeredCount > 0
            : true;

  async function computeRisk(nextAnswers: Record<string, string>) {
    if (Object.keys(nextAnswers).length === 0) return;
    setLoading(true);
    try {
      const result = await api.riskScore(nextAnswers);
      setRiskResult(result);
      setProfile({ riskScore: result.score, riskBand: result.band, answers: nextAnswers });
    } finally {
      setLoading(false);
    }
  }

  function finish() {
    setProfile({ answers });
    router.push("/recommendations?generate=1");
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Build your investor profile</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Five short steps. Everything downstream is computed from your answers — nothing is assumed.
        </p>
      </header>

      <ol className="mb-6 flex flex-wrap gap-2" aria-label="Progress">
        {STEPS.map((label, index) => (
          <li key={label}>
            <button
              onClick={() => index < step && setStep(index)}
              disabled={index > step}
              className={cn(
                "flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition-colors",
                index === step
                  ? "border-accent-300 bg-accent-50 font-medium text-accent-800"
                  : index < step
                    ? "border-line bg-surface text-ink-muted"
                    : "border-line bg-surface text-ink-subtle",
              )}
            >
              <span className="num">{index + 1}</span>
              {label}
            </button>
          </li>
        ))}
      </ol>

      <Card>
        {step === 0 ? (
          <>
            <CardHeader title="Investment amount" subtitle="How much are you investing, and how much will you add?" />
            <CardBody className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Initial investment" hint="One-time amount invested today">
                  <TextInput
                    inputMode="numeric"
                    value={profile.initialInvestment}
                    onChange={(event) =>
                      setProfile({ initialInvestment: Math.max(0, Number(event.target.value) || 0) })
                    }
                  />
                </Field>
                <Field label="Monthly contribution" hint="Added at the end of each month">
                  <TextInput
                    inputMode="numeric"
                    value={profile.monthlyContribution}
                    onChange={(event) =>
                      setProfile({ monthlyContribution: Math.max(0, Number(event.target.value) || 0) })
                    }
                  />
                </Field>
              </div>
              <Field
                label="Annual contribution increase (optional, %)"
                hint="Annual step-up applied to the monthly contribution, e.g. 10"
              >
                <TextInput
                  inputMode="decimal"
                  value={profile.annualContributionIncrease * 100}
                  onChange={(event) =>
                    setProfile({
                      annualContributionIncrease: Math.max(0, Number(event.target.value) || 0) / 100,
                    })
                  }
                />
              </Field>
              <p className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-ink-muted">
                Total invested over {profile.horizonYears} years (excluding any step-up):{" "}
                <strong className="num font-semibold text-ink">
                  {formatINR(
                    profile.initialInvestment + profile.monthlyContribution * 12 * profile.horizonYears,
                    { compact: true },
                  )}
                </strong>
              </p>
            </CardBody>
          </>
        ) : null}

        {step === 1 ? (
          <>
            <CardHeader title="Investment horizon" subtitle="When will you start using this money?" />
            <CardBody className="space-y-4">
              <RadioGroup
                name="horizon"
                value={String(profile.horizonYears)}
                options={[
                  { value: "1", label: "Less than 1 year" },
                  { value: "3", label: "1–3 years" },
                  { value: "5", label: "3–5 years" },
                  { value: "10", label: "5–10 years" },
                  { value: "15", label: "10+ years" },
                ]}
                onChange={(value) => setProfile({ horizonYears: Number(value) })}
                columns={2}
              />
              <Field label="Or enter an exact number of years">
                <TextInput
                  inputMode="numeric"
                  value={profile.horizonYears}
                  onChange={(event) =>
                    setProfile({ horizonYears: Math.min(50, Math.max(0.5, Number(event.target.value) || 1)) })
                  }
                />
              </Field>
            </CardBody>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <CardHeader title="Objective" subtitle="Pick the primary goal. A secondary goal is optional." />
            <CardBody className="space-y-5">
              <div>
                <p className="label mb-2">Primary objective</p>
                <RadioGroup
                  name="objective"
                  value={profile.objective}
                  options={objectives.map((objective) => ({
                    value: objective.id,
                    label: objective.label,
                    description: objective.description,
                  }))}
                  onChange={(value) => setProfile({ objective: value })}
                  columns={2}
                />
              </div>
              <div>
                <p className="label mb-2">Secondary objective (optional)</p>
                <Select
                  value={profile.secondaryObjective ?? ""}
                  onChange={(event) => setProfile({ secondaryObjective: event.target.value || undefined })}
                >
                  <option value="">None</option>
                  {objectives
                    .filter((objective) => objective.id !== profile.objective)
                    .map((objective) => (
                      <option key={objective.id} value={objective.id}>
                        {objective.label}
                      </option>
                    ))}
                </Select>
              </div>
            </CardBody>
          </>
        ) : null}

        {step === 3 ? (
          <>
            <CardHeader
              title="Risk tolerance"
              subtitle="We derive a risk score from your answers rather than asking you to label yourself."
            />
            <CardBody className="space-y-6">
              {questions.length === 0 ? (
                <p className="flex items-center gap-2 text-sm text-ink-muted">
                  <Spinner /> Loading questions…
                </p>
              ) : (
                questions.map((question) => (
                  <fieldset key={question.id}>
                    <legend className="mb-2 text-sm font-medium text-ink">{question.prompt}</legend>
                    <RadioGroup
                      name={question.id}
                      value={answers[question.id] ?? null}
                      options={question.options.map((option) => ({ value: option.id, label: option.label }))}
                      onChange={(value) => {
                        const next = { ...answers, [question.id]: value };
                        setAnswers(next);
                        void computeRisk(next);
                      }}
                      columns={2}
                    />
                  </fieldset>
                ))
              )}

              {riskResult ? (
                <div className="rounded-lg border border-accent-200 bg-accent-50 p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="num text-2xl font-semibold text-accent-800">
                      {Math.round(riskResult.score)}
                    </span>
                    <span
                      className={cn(
                        "rounded-md border px-2 py-0.5 text-xs font-medium",
                        riskBandTone(riskResult.band),
                      )}
                    >
                      {riskResult.band}
                    </span>
                    <span className="text-xs text-accent-800">
                      {answeredCount} of {questions.length} answered{loading ? " · recalculating…" : ""}
                    </span>
                  </div>
                  {riskResult.explanation ? (
                    <p className="mt-2 text-xs leading-relaxed text-accent-900">{riskResult.explanation}</p>
                  ) : null}
                </div>
              ) : null}
            </CardBody>
          </>
        ) : null}

        {step === 4 ? (
          <>
            <CardHeader
              title="Asset universe"
              subtitle="Choose which assets the optimiser may use. Leave everything selected for the full universe."
            />
            <CardBody className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => setUniverse([])}>
                  Use entire universe
                </Button>
                <span className="text-xs text-ink-muted">
                  {universe.length ? `${universe.length} selected` : `All ${assets.length} assets`}
                </span>
              </div>
              <div className="max-h-80 overflow-y-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <caption className="sr-only">
                    Select the assets the optimiser is allowed to allocate to
                  </caption>
                  <thead className="sticky top-0 bg-stone-50 text-left text-xs text-ink-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-medium">Asset</th>
                      <th scope="col" className="px-3 py-2 font-medium">Class</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Return</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Volatility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((asset) => {
                      const checked = universe.length === 0 || universe.includes(asset.symbol);
                      return (
                        <tr key={asset.symbol} className="border-t border-line">
                          <td className="px-3 py-2">
                            <label className="flex items-start gap-2">
                              <input
                                type="checkbox"
                                className="mt-0.5 h-4 w-4 accent-accent-700"
                                checked={checked}
                                onChange={(event) => {
                                  const base = universe.length ? universe : assets.map((item) => item.symbol);
                                  const next = event.target.checked
                                    ? [...base, asset.symbol]
                                    : base.filter((symbol) => symbol !== asset.symbol);
                                  setUniverse(next);
                                }}
                              />
                              <span>
                                <span className="block font-medium text-ink">{asset.name}</span>
                                <span className="block text-xs text-ink-subtle">{asset.symbol}</span>
                              </span>
                            </label>
                          </td>
                          <td className="px-3 py-2 text-ink-muted capitalize">
                            {asset.assetClass.replace(/_/g, " ")}
                          </td>
                          <td className="num px-3 py-2 text-right">{formatPercent(asset.annualizedReturn)}</td>
                          <td className="num px-3 py-2 text-right">{formatPercent(asset.volatility)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </>
        ) : null}

        <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-4 sm:px-6">
          <Button variant="ghost" onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={step === 0}>
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={() => setStep((value) => value + 1)} disabled={!canAdvance}>
              Continue
            </Button>
          ) : (
            <Button onClick={finish}>Generate my investment plans</Button>
          )}
        </div>
      </Card>

      <Disclaimer className="mt-4">
        Your answers build a self-reported risk profile used to size the optimiser&apos;s risk budget.
        This is not a regulated suitability assessment, and nothing produced here is personalised
        financial advice.
      </Disclaimer>
    </div>
  );
}
