"""Investor risk questionnaire and scoring.

Questions live here (not in the UI) so the scoring logic and the wording can
never drift apart, and so the score is computed server-side and deterministically.
"""
from __future__ import annotations

__all__ = ["QUESTIONS", "risk_profile", "OBJECTIVES", "HORIZONS", "PROFILE_BANDS"]

HORIZONS = [
    {"id": "lt1", "label": "Less than 1 year", "years": 1},
    {"id": "1_3", "label": "1-3 years", "years": 3},
    {"id": "3_5", "label": "3-5 years", "years": 5},
    {"id": "5_10", "label": "5-10 years", "years": 10},
    {"id": "10p", "label": "10+ years", "years": 15},
]

OBJECTIVES = [
    {"id": "capital_preservation", "label": "Capital Preservation",
     "description": "Protect the value of your capital; accept lower expected growth."},
    {"id": "balanced_growth", "label": "Balanced Growth",
     "description": "A measured mix of growth and stability."},
    {"id": "wealth_creation", "label": "Long-Term Wealth Creation",
     "description": "Grow capital over a long horizon, accepting meaningful volatility."},
    {"id": "income", "label": "Income",
     "description": "Generate regular income from the portfolio."},
    {"id": "inflation_protection", "label": "Inflation Protection",
     "description": "Preserve purchasing power against rising prices."},
    {"id": "maximum_growth", "label": "Maximum Growth",
     "description": "Maximise long-run growth and accept large drawdowns."},
]

QUESTIONS = [
    {
        "id": "drawdown_reaction",
        "weight": 0.25,
        "prompt": "If your ₹10 lakh portfolio temporarily falls to ₹8 lakh, what would you most likely do?",
        "dimension": "Loss tolerance",
        "options": [
            {"id": "sell", "label": "Sell immediately", "score": 0},
            {"id": "reduce", "label": "Reduce some exposure", "score": 30},
            {"id": "hold", "label": "Hold and wait", "score": 65},
            {"id": "add", "label": "Invest more", "score": 100},
        ],
    },
    {
        "id": "loss_tolerance",
        "weight": 0.15,
        "prompt": "What is the largest one-year decline you could tolerate without abandoning your plan?",
        "dimension": "Loss tolerance",
        "options": [
            {"id": "5", "label": "Up to 5%", "score": 0},
            {"id": "10", "label": "Up to 10%", "score": 25},
            {"id": "20", "label": "Up to 20%", "score": 60},
            {"id": "35", "label": "Up to 35%", "score": 85},
            {"id": "50", "label": "More than 50%", "score": 100},
        ],
    },
    {
        "id": "horizon",
        "weight": 0.15,
        "prompt": "When do you expect to start using this money?",
        "dimension": "Investment horizon",
        "options": [
            {"id": "lt1", "label": "Within 1 year", "score": 0},
            {"id": "1_3", "label": "In 1-3 years", "score": 25},
            {"id": "3_5", "label": "In 3-5 years", "score": 50},
            {"id": "5_10", "label": "In 5-10 years", "score": 75},
            {"id": "10p", "label": "Not for 10+ years", "score": 100},
        ],
    },
    {
        "id": "income_stability",
        "weight": 0.10,
        "prompt": "How stable is your income?",
        "dimension": "Income stability",
        "options": [
            {"id": "unstable", "label": "Very unpredictable", "score": 0},
            {"id": "somewhat", "label": "Somewhat unpredictable", "score": 33},
            {"id": "stable", "label": "Stable", "score": 66},
            {"id": "very_stable", "label": "Very stable", "score": 100},
        ],
    },
    {
        "id": "liquidity_need",
        "weight": 0.10,
        "prompt": "How soon might you need to withdraw a large part of this money?",
        "dimension": "Liquidity requirement",
        "options": [
            {"id": "6m", "label": "Within 6 months", "score": 0},
            {"id": "1y", "label": "Within a year", "score": 33},
            {"id": "3y", "label": "Within 3 years", "score": 66},
            {"id": "never", "label": "Not for many years", "score": 100},
        ],
    },
    {
        "id": "experience",
        "weight": 0.10,
        "prompt": "How would you describe your investment experience?",
        "dimension": "Previous experience",
        "options": [
            {"id": "none", "label": "None", "score": 0},
            {"id": "some", "label": "Some (FDs, mutual funds)", "score": 33},
            {"id": "moderate", "label": "Moderate (direct equities)", "score": 66},
            {"id": "extensive", "label": "Extensive (multi-asset, derivatives)", "score": 100},
        ],
    },
    {
        "id": "volatility_reaction",
        "weight": 0.15,
        "prompt": "How do you feel when markets fall sharply?",
        "dimension": "Reaction to volatility",
        "options": [
            {"id": "anxious", "label": "Very anxious - I want out", "score": 0},
            {"id": "uneasy", "label": "Uneasy, but I stay invested", "score": 40},
            {"id": "comfortable", "label": "Comfortable - volatility is normal", "score": 75},
            {"id": "opportunity", "label": "I see it as an opportunity", "score": 100},
        ],
    },
]

PROFILE_BANDS = [
    (25, "Conservative"),
    (50, "Moderate Conservative"),
    (70, "Moderate"),
    (85, "Growth"),
    (100, "Aggressive"),
]


def risk_profile(answers: dict[str, str]) -> dict:
    """Compute a 0-100 risk score from the questionnaire answers."""
    total_weight = 0.0
    weighted = 0.0
    breakdown = []
    unanswered = []
    for question in QUESTIONS:
        choice = answers.get(question["id"])
        option = next((o for o in question["options"] if o["id"] == choice), None)
        if option is None:
            unanswered.append(question["id"])
            continue
        weighted += option["score"] * question["weight"]
        total_weight += question["weight"]
        breakdown.append(
            {
                "id": question["id"],
                "dimension": question["dimension"],
                "answer": option["label"],
                "score": option["score"],
                "weight": question["weight"],
            }
        )
    if total_weight == 0:
        raise ValueError("No questionnaire answers were supplied")
    score = weighted / total_weight
    # Unanswered questions slightly shrink confidence, they never inflate the score.
    score = round(float(min(max(score, 0.0), 100.0)), 1)
    band = next(label for upper, label in PROFILE_BANDS if score <= upper)
    return {
        "score": score,
        "band": band,
        "breakdown": breakdown,
        "unanswered": unanswered,
        "explanation": _explain(score, band, breakdown),
    }


def _explain(score: float, band: str, breakdown: list[dict]) -> str:
    dimensions = ", ".join(sorted({b["dimension"] for b in breakdown}))
    return (
        f"Your answers across {len(breakdown)} questions ({dimensions}) produce a risk score of "
        f"{score:.0f}/100, which maps to a {band} profile. This is a self-reported indicator used to "
        "size the risk budget for the optimiser; it is not a regulated suitability assessment."
    )
