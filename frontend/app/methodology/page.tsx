import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { MethodSection } from "@/components/methodology/MethodSection";

export const metadata = {
  title: "Methodology — Portfolio Quant",
};

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Methodology</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Every number in this application is computed by a tested function in the analytics engine.
          This page explains each one in plain language first, with the technical detail underneath.
        </p>
      </header>

      <Card>
        <CardBody>
          <p className="text-sm leading-relaxed text-ink-muted">
            Nothing here is hard-coded into a chart or a page. Metrics are produced by the backend
            analytics module, each covered by unit tests with known expected values, and each
            returned alongside the assumptions used to compute it.
          </p>
        </CardBody>
      </Card>

      <MethodSection
        title="Returns"
        plain="A return is simply how much a price moved. We use two conventions and always say which one: simple returns for compounding money, log returns for statistics."
        technical={[
          "Simple return: r_t = P_t / P_(t-1) − 1. This is what compounds: a portfolio's growth is the product of (1 + r_t).",
          "Log return: ln(P_t / P_(t-1)). Additive across time, convenient for statistical work.",
          "The engine never silently picks one — every function takes the convention as an argument and every API response reports it.",
          "Zero or negative prices are rejected with an error rather than repaired, because they indicate bad data, not an extreme market.",
        ]}
        formula={["r_t = P_t / P_{t-1} - 1", "log return = ln(P_t / P_{t-1})"]}
      />

      <MethodSection
        title="Annualised return and CAGR"
        plain="Annualised return turns a daily average into a yearly figure. CAGR is the actual compounded yearly growth you would have experienced."
        technical={[
          "Arithmetic annualised return = mean(daily return) × 252. This is the single-period expectation used by mean-variance mathematics, so it is what 'expected return' means in this application.",
          "CAGR = (final / initial)^(1 / years) − 1. It is the realised geometric growth rate and is always less than or equal to the arithmetic mean.",
          "Expected return on a page is arithmetic; backtests report both arithmetic and CAGR, clearly separated.",
          "CAGR returns 'not available' rather than a misleading number when the period is zero, negative, or the value never had a positive starting point.",
        ]}
        formula={["Annualised = mean(r) × trading_days", "CAGR = (V_end / V_start)^(1/years) − 1"]}
      />

      <MethodSection
        title="Volatility"
        plain="Volatility measures how much returns swing around. We calculate the standard deviation of daily returns and scale it up to a year."
        technical={[
          "Annualised volatility = standard deviation of daily returns (sample, ddof = 1) × √252.",
          "252 is an assumption about the number of trading days in a year and is configurable, not hard-coded.",
          "Volatility is floored at zero: portfolio variance can never be reported as negative, even if floating-point noise would produce a tiny negative eigenvalue.",
        ]}
        formula={["σ_annual = σ_daily × √252"]}
      />

      <MethodSection
        title="Sharpe ratio"
        plain="How much return you received for each unit of risk taken. Higher is better."
        technical={[
          "Sharpe = (annualised return − risk-free rate) ÷ annualised volatility.",
          "The risk-free rate is a configurable assumption (default 6.5% for INR), never a hard-coded constant.",
          "We use the arithmetic annualised return so the ratio is consistent with the mean-variance framework used by the optimiser. A CAGR-based Sharpe is also reported where a backtest is shown.",
          "When volatility is zero the ratio is mathematically undefined; the engine returns 'not available' instead of an infinite number, unless excess return is also zero (then 0).",
        ]}
        formula={["Sharpe = (R_p − R_f) / σ_p"]}
      />

      <MethodSection
        title="Sortino ratio"
        plain="Like Sharpe, but it only penalises downside moves — losses are what most investors actually care about."
        technical={[
          "Downside deviation = √( mean( min(r − MAR, 0)² ) ) over the full sample, where MAR is the minimum acceptable return.",
          "Sortino = (annualised return − MAR) ÷ downside deviation.",
          "We use the full-sample convention (dividing by the total number of observations, not just the losing ones), which is the standard Sortino–Satchell definition and keeps the metric comparable across assets.",
          "Zero downside deviation is handled explicitly rather than dividing by zero.",
        ]}
        formula={["DD = √( mean( min(r − MAR, 0)² ) )", "Sortino = (R_p − MAR) / DD"]}
      />

      <MethodSection
        title="Drawdown and recovery"
        plain="A drawdown is how far the portfolio fell from its highest point. Recovery is how long it took to climb back."
        technical={[
          "Drawdown at time t = V_t / running_max(V) − 1, always ≤ 0.",
          "Maximum drawdown is the worst such value in the sample and is reported as a negative number.",
          "Recovery is measured in periods from the trough back to the previous peak; if the portfolio had not recovered by the end of the data, the API says so rather than inventing a value.",
          "Drawdown is measured on the time-weighted curve. On a curve that includes contributions, fresh cash would mask the fall and understate the risk.",
          "Ulcer index (root-mean-square drawdown) is also reported: it penalises deep and long drawdowns, not just the single worst point.",
        ]}
        formula={["DD_t = V_t / max(V_0..V_t) − 1"]}
      />

      <MethodSection
        title="Portfolio mathematics"
        plain="A portfolio's expected return is the weighted average of its parts — but its risk is not, because diversification reduces risk."
        technical={[
          "Expected return: E(R_p) = Σ w_i E(R_i).",
          "Portfolio variance: σ_p² = wᵀ Σ w, where Σ is the covariance matrix. Volatility is its square root.",
          "This is why a portfolio's volatility is almost always below the weighted average of its holdings' volatilities — the gap is the diversification benefit.",
          "The covariance matrix is projected onto the nearest positive semi-definite matrix before use, so numerical noise can never produce a negative variance.",
        ]}
        formula={["E(R_p) = Σ w_i E(R_i)", "σ_p² = wᵀ Σ w"]}
      />

      <MethodSection
        title="Risk contribution"
        plain="Equal money is not equal risk. A 20% holding of a volatile, highly correlated asset can carry far more than 20% of the portfolio's risk."
        technical={[
          "Marginal contribution to risk of asset i: (Σ w)_i / σ_p.",
          "Component contribution: w_i × marginal contribution.",
          "By Euler's theorem the component contributions sum exactly to portfolio volatility, so the shares reported always add to 100%.",
          "The diversification ratio — weighted average volatility ÷ portfolio volatility — summarises the whole effect in one number above 1.0.",
        ]}
        formula={["MCR_i = (Σ w)_i / σ_p", "RC_i = w_i × MCR_i", "Σ RC_i = σ_p"]}
      />

      <MethodSection
        title="Correlation"
        plain="Correlation measures whether two assets move together (positive), independently (near zero) or in opposite directions (negative)."
        technical={[
          "Pearson correlation of daily returns, computed pairwise-complete so one asset's missing day does not silently drop another asset's data.",
          "Values are clipped to [−1, +1] to remove floating-point drift.",
          "Correlations can be computed over 30-day, 90-day, 1-year, 3-year, 5-year or full-history windows because the relationship is not stable over time.",
          "The correlation heatmap always prints the numeric value in each cell, so the information is never conveyed by colour alone.",
        ]}
        formula={["ρ = cov(X, Y) / (σ_X σ_Y)"]}
      />

      <MethodSection
        title="Value at Risk and Expected Shortfall"
        plain="VaR answers 'how bad is a bad day?'. Expected shortfall answers 'if it is a bad day, how bad on average?'."
        technical={[
          "Historical VaR at 95%: the 5th percentile of realised daily returns, reported as a positive loss magnitude. Non-parametric — it is simply what happened.",
          "Historical CVaR (expected shortfall): the average of the returns at or beyond that percentile. Always at least as severe as VaR.",
          "Parametric (Gaussian) VaR and CVaR are also computed and labelled MODEL-BASED. They assume normally distributed returns, which understates tail risk.",
          "Historical and model-based figures are never mixed or presented interchangeably in the interface.",
        ]}
        formula={["VaR_95 = −quantile_5%(r)", "CVaR_95 = −mean(r | r ≤ quantile_5%)"]}
      />

      <MethodSection
        title="Optimization strategies"
        plain="The optimiser searches for the best allocation under your constraints. Six different definitions of 'best' are available."
        technical={[
          "Minimum variance: minimise wᵀΣw. The lowest-risk allocation available.",
          "Maximum Sharpe: maximise (wᵀμ − r_f) / √(wᵀΣw).",
          "Maximum return under a risk cap: maximise wᵀμ subject to √(wᵀΣw) ≤ cap.",
          "Risk parity: equalise each asset's contribution to portfolio risk, so no single holding dominates the risk budget.",
          "Maximum diversification: maximise (w·σ_assets) / √(wᵀΣw).",
          "Minimum CVaR: minimise the average loss on the worst days, subject to the same constraints.",
          "All six are solved with sequential quadratic programming over the identical constraint set (weight bounds, asset-class and sector limits, volatility and drawdown caps, exclusions), so results are directly comparable.",
          "Results are re-projected onto the bounds and re-checked after solving; a solution that violates any constraint is rejected rather than returned.",
        ]}
      />

      <MethodSection
        title="The efficient frontier"
        plain="For each level of expected return, the frontier shows the lowest risk available. Portfolios below the line are leaving risk-reduction on the table."
        technical={[
          "For a grid of target returns, the frontier solves for the minimum-variance portfolio that achieves exactly that return, subject to your constraints.",
          "Points that cannot be achieved within the constraints are omitted rather than interpolated.",
          "The minimum-variance portfolio and the maximum-Sharpe (tangency) portfolio are marked distinctly.",
        ]}
      />

      <MethodSection
        title="How plans are generated and ranked"
        plain="Thousands of candidate portfolios are generated, filtered, scored, and then the five most different and highest-scoring become your plans."
        technical={[
          "Tens of thousands of candidate allocations are generated: randomised long-only portfolios honouring every bound, plus deterministic seeds from all six optimisation strategies.",
          "Every candidate is screened with vectorised matrix algebra on expected return, volatility and Sharpe.",
          "A diverse subset (a few hundred, spread across the risk spectrum) is then scored on the full path-dependent metrics — drawdown, Sortino, CVaR — using a batched (T × K) computation rather than one portfolio at a time.",
          "Scoring weights: 35% risk-adjusted return, 25% downside risk, 15% diversification, 10% drawdown, 10% objective alignment, 5% liquidity. These weights are configurable.",
          "One plan is then selected per risk band (Capital Preservation → Growth) with a diversity penalty that rejects any portfolio too similar to one already chosen, plus a 'Risk-Optimized' plan chosen purely on risk-adjusted score.",
          "Finally, economically meaningless positions are trimmed and every metric recomputed from the trimmed weights, so the numbers shown always describe exactly the allocation shown.",
          "Your risk-profile score sizes the risk budget: the feasible volatility range is scaled to your profile, with a floor so that every investor still sees a meaningful spread of options.",
        ]}
      />

      <MethodSection
        title="The Platform Risk Score"
        plain="A 0–100 summary of how risky a portfolio has been. It is transparent and inspectable — not an industry-standard rating."
        technical={[
          "Eight inputs, each normalised to 0–1 against a documented band: volatility (22%), maximum drawdown (20%), downside deviation (13%), daily VaR (10%), equity exposure (13%), concentration (7%), asset-class concentration (8%) and illiquidity (7%).",
          "Concentration uses the normalised Herfindahl index of weights; illiquidity is one minus the weighted average liquidity score.",
          "Bands: 0–20 Very Low, 21–40 Low, 41–60 Moderate, 61–80 High, 81–100 Very High.",
          "The full component breakdown, including each input's weight and contribution to the score, is shown on every portfolio page.",
          "It is a platform-defined composite. It is not a regulated risk rating, a SEBI riskometer, or a substitute for professional advice.",
        ]}
      />

      <MethodSection
        title="Backtesting, and why performance and contributions are separated"
        plain="A backtest replays an allocation through history. When you add money monthly, the account balance grows for two reasons — investment performance and your own deposits. We report those separately."
        technical={[
          "The simulator walks forward one period at a time. At each step it applies that period's realised returns to the weights carried in from the previous step, so it never uses information it could not have had.",
          "Time-weighted return compounds the periodic returns only. Cash inflows cannot inflate it.",
          "Money-weighted return (IRR) is solved separately by bisection on the net present value of the contribution schedule.",
          "The account value curve is reported alongside the performance curve so you can see both.",
          "Rebalancing is modelled explicitly — buy & hold, monthly, quarterly, semi-annual, annual or threshold-band — with a configurable transaction cost in basis points of traded notional.",
          "Taxes, slippage and market impact are not modelled. That is an explicit limitation, not an oversight.",
        ]}
      />

      <MethodSection
        title="Walk-forward (out-of-sample) validation"
        plain="Optimising and evaluating on the same data flatters the result. Walk-forward splits them."
        technical={[
          "The optimiser is fitted only on the training window, then the resulting weights are frozen and applied to a strictly later test window.",
          "The API asserts that the test window begins after the training window ends.",
          "In-sample and out-of-sample results are labelled separately and shown side by side. A large gap between them is a warning that the fit may not persist.",
        ]}
      />

      <MethodSection
        title="Monte Carlo simulation"
        plain="Monte Carlo runs thousands of possible futures through the same statistical model and reports the spread of outcomes."
        technical={[
          "Three methods: normal (parametric, using the historical mean vector and covariance matrix), Student-t (fat tails, 5 degrees of freedom), and a stationary block bootstrap that resamples realised history.",
          "All methods are seeded: the same seed reproduces the same paths exactly.",
          "Contributions are added each period and can grow by an annual step-up; the portfolio is assumed rebalanced to target weights each period.",
          "Percentile bands (P10–P90) and final-value percentiles are reported, along with the probability of finishing below the amount invested.",
          "Costs and taxes are not modelled in the projection.",
          "These are illustrative model scenarios. They are not a forecast and not a range of guaranteed outcomes.",
        ]}
      />

      <MethodSection
        title="Stress testing"
        plain="Two clearly different things: hypothetical shocks you define, and the worst periods that actually happened."
        technical={[
          "Scenario shocks are instantaneous and applied by asset class: the portfolio impact is the weighted sum of each asset's shock. Assumptions are editable and labelled ILLUSTRATIVE.",
          "The model deliberately assumes nothing else changes; it does not model correlations shifting, liquidity disappearing or forced selling.",
          "Historical stress windows are OBSERVED: the deepest rolling realised losses for that exact allocation, replayed from the data.",
          "The two are never mixed or presented as equivalent.",
        ]}
      />

      <MethodSection
        title="Data quality"
        plain="Before any analysis, the data is checked. Problems are reported and affected assets are excluded — never silently patched."
        technical={[
          "Checks: duplicate dates, unsorted dates, missing sessions, missing prices, zero or negative prices, non-finite values, extreme unexplained jumps, stale (unchanged) prices, calendar mismatches, currency mismatches, late-listing and early-termination (delisting / survivorship) signals.",
          "Assets that fail a blocking check are quarantined with a reason and excluded from the analysis; the API reports which ones and why.",
          "A 0–100 score with a grade is computed from the severity and breadth of issues.",
          "The pipeline never forward-fills, interpolates or otherwise invents a price.",
        ]}
      />

      <MethodSection
        title="Known limitations"
        plain="Stated plainly, because a tool that hides its limits is not a decision-support tool."
        technical={[
          "Optimised portfolios are sensitive to inputs: small changes in the sample period can produce materially different allocations.",
          "Historical correlations are not stable and tend to converge towards 1 in crises — exactly when diversification is needed.",
          "The demo data is synthetic. Any resemblance to real securities is limited to the instrument names used for illustration.",
          "Taxes, slippage, expense ratios and market impact are not modelled in backtests or projections.",
          "Derivatives are analytical only; no instrument in this application is tradable through it.",
          "The risk score is a platform composite, not a regulated measure.",
          "This is analysis and education, not personalised regulated advice.",
        ]}
      />

      <Card>
        <CardHeader title="Verification" />
        <CardBody className="space-y-2 text-sm leading-relaxed text-ink-muted">
          <p>
            Every formula above is implemented in the backend analytics module and covered by unit
            tests with known expected values — including the edge cases the specification calls out:
            weights summing to 100%, non-negative portfolio variance, non-negative volatility,
            Sharpe and Sortino with zero denominators, drawdown never positive, CAGR with invalid
            periods, seeded reproducibility, and out-of-sample results being genuinely out of
            sample.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Badge tone="positive">Deterministic</Badge>
            <Badge tone="positive">Unit tested</Badge>
            <Badge tone="positive">Assumptions disclosed</Badge>
            <Badge tone="neutral">No hard-coded metrics</Badge>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
