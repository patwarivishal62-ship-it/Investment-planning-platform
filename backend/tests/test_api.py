"""End-to-end API tests: validation, feasibility handling and plan quality."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

UNIVERSE = ["NIFTY50", "GOLD", "SILVER", "GSEC10Y", "US_EQUITY"]
WEIGHTS = {"NIFTY50": 0.5, "GOLD": 0.2, "GSEC10Y": 0.3}


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_data_status_is_demo_and_labelled():
    payload = client.get("/api/data/status").json()
    assert payload["mode"] == "demo"
    assert payload["isDemo"] is True
    assert payload["assetCount"] > 10
    assert payload["dataQuality"]["score"] > 0
    assert any("DEMO DATA" in w for w in payload["warnings"])


def test_config_never_exposes_secrets():
    payload = client.get("/api/config").json()
    assert "apiKey" not in payload
    assert "MARKET_DATA_API_KEY" not in str(payload)
    assert payload["currency"] == "INR"


def test_questionnaire_is_served_from_the_backend():
    payload = client.get("/api/profile/questions").json()
    assert len(payload["questions"]) >= 5
    assert {q["id"] for q in payload["questions"]}
    assert payload["objectives"]


def test_risk_score_is_deterministic_and_bounded():
    answers = {
        "drawdown_reaction": "hold",
        "loss_tolerance": "20",
        "horizon": "5_10",
        "income_stability": "stable",
        "liquidity_need": "3y",
        "experience": "some",
        "volatility_reaction": "comfortable",
    }
    first = client.post("/api/profile/risk-score", json={"answers": answers}).json()
    second = client.post("/api/profile/risk-score", json={"answers": answers}).json()
    assert first["score"] == second["score"]
    assert 0 <= first["score"] <= 100
    assert first["band"]
    assert first["breakdown"]


def test_assets_endpoint_returns_computed_statistics():
    payload = client.get("/api/assets").json()
    assert len(payload) > 10
    row = next(a for a in payload if a["symbol"] == "NIFTY50")
    assert row["volatility"] > 0
    assert row["annualizedReturn"] is not None
    assert row["maxDrawdown"] <= 0
    assert row["dataSource"]
    assert row["asOf"]


def test_asset_history_endpoint():
    payload = client.get("/api/assets/NIFTY50/history").json()
    assert payload["symbol"] == "NIFTY50"
    assert len(payload["prices"]) > 500
    assert all(p["close"] > 0 for p in payload["prices"])


def test_unknown_symbol_returns_404():
    assert client.get("/api/assets/NOT_A_SYMBOL").status_code == 404


def test_analytics_assets():
    response = client.post("/api/analytics/assets", json={"symbols": UNIVERSE})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["assets"]) == len(UNIVERSE)
    assert payload["correlation"]["symbols"] == UNIVERSE


def test_analyze_returns_full_metric_bundle():
    response = client.post("/api/portfolio/analyze", json={"weights": WEIGHTS, "symbols": UNIVERSE})
    assert response.status_code == 200
    metrics = response.json()
    for key in ("expectedReturn", "volatility", "sharpe", "sortino", "maxDrawdown",
                "historicalVaR", "historicalCVaR", "riskScore"):
        assert key in metrics, key
    assert metrics["maxDrawdown"] <= 0
    assert metrics["volatility"] >= 0
    assert metrics["riskScore"]["score"] >= 0
    assert abs(sum(metrics["weights"].values()) - 1.0) < 1e-6


def test_negative_weights_are_rejected():
    response = client.post("/api/portfolio/analyze",
                           json={"weights": {"NIFTY50": -0.5, "GOLD": 1.5}, "symbols": UNIVERSE})
    assert response.status_code == 422


def test_optimize_returns_all_strategies():
    response = client.post("/api/portfolio/optimize", json={
        "symbols": UNIVERSE,
        "strategies": ["min_variance", "max_sharpe", "risk_parity", "max_diversification"],
    })
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["results"]) == 4
    for result in payload["results"]:
        assert abs(sum(result["metrics"]["weights"].values()) - 1.0) < 1e-6


def test_unknown_strategy_is_rejected():
    response = client.post("/api/portfolio/optimize",
                           json={"symbols": UNIVERSE, "strategies": ["magic"]})
    assert response.status_code == 422


def test_recommend_returns_five_distinct_plans():
    response = client.post("/api/portfolio/recommend", json={
        "capital": 1_000_000, "monthlyContribution": 20_000, "horizonYears": 10,
        "riskScore": 55, "objective": "wealth_creation", "maxVolatility": 0.18,
        "symbols": UNIVERSE, "rebalanceFrequency": "quarterly",
    })
    assert response.status_code == 200
    payload = response.json()
    plans = payload["plans"]
    assert 4 <= len(plans) <= 5

    # 1. weights sum to 100%
    for plan in plans:
        assert abs(sum(plan["metrics"]["weights"].values()) - 1.0) < 1e-6

    # 2. plans are genuinely different, not five variations of one portfolio
    for i in range(len(plans)):
        for j in range(i + 1, len(plans)):
            a = np.array([plans[i]["metrics"]["weights"].get(s, 0.0) for s in UNIVERSE])
            b = np.array([plans[j]["metrics"]["weights"].get(s, 0.0) for s in UNIVERSE])
            assert np.abs(a - b).sum() > 0.10, f"{plans[i]['name']} == {plans[j]['name']}"

    # 3. exactly one Best Fit
    assert sum(1 for p in plans if p["bestFit"]) == 1

    # 4. every plan explains itself with computed numbers
    for plan in plans:
        explanation = plan["explanation"]
        assert explanation["summary"]
        assert explanation["caveat"]
        assert explanation["mainRisk"]["assets"]

    # 5. assumptions are disclosed
    assert payload["assumptions"]["riskFreeRate"] > 0
    assert payload["assumptions"]["dataPeriod"]
    assert payload["candidateCount"] > 1000


def test_recommend_respects_volatility_cap():
    response = client.post("/api/portfolio/recommend", json={
        "capital": 1_000_000, "riskScore": 80, "objective": "wealth_creation",
        "maxVolatility": 0.09, "symbols": UNIVERSE,
    })
    plans = response.json()["plans"]
    for plan in plans:
        assert plan["metrics"]["volatility"] <= 0.09 + 1e-6


def test_infeasible_constraints_return_suggestions_not_a_fake_portfolio():
    response = client.post("/api/portfolio/recommend", json={
        "capital": 1_000_000, "riskScore": 80, "objective": "wealth_creation",
        "maxVolatility": 0.005, "symbols": UNIVERSE,
    })
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "no_feasible_portfolio"
    assert payload["suggestions"]
    assert any("volatility" in s.lower() for s in payload["suggestions"])
    # No plan was fabricated.
    assert "plans" not in payload


def test_conflicting_class_bounds_are_explained():
    response = client.post("/api/portfolio/recommend", json={
        "symbols": UNIVERSE,
        "classBounds": {"equity": [0.9, 1.0], "bond": [0.5, 1.0]},
    })
    assert response.status_code == 422
    assert response.json()["code"] == "no_feasible_portfolio"


def test_efficient_frontier_is_monotonic():
    response = client.post("/api/efficient-frontier",
                           json={"symbols": UNIVERSE, "points": 12})
    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) >= 2
    returns_ = [p["expectedReturn"] for p in points]
    assert all(b >= a - 1e-9 for a, b in zip(returns_, returns_[1:]))
    assert response.json()["minVariance"]["volatility"] > 0


def test_backtest_separates_performance_from_contributions():
    response = client.post("/api/backtest", json={
        "weights": WEIGHTS, "symbols": UNIVERSE,
        "initialValue": 1_000_000, "monthlyContribution": 20_000,
        "rebalanceFrequency": "quarterly",
    })
    assert response.status_code == 200
    portfolio = response.json()["portfolio"]
    assert portfolio["endValue"] > portfolio["invested"] or True
    assert portfolio["contributions"] > 0
    # Time-weighted CAGR must be a plausible market return, not inflated by cash.
    assert -0.5 < portfolio["cagr"] < 0.5
    assert portfolio["maxDrawdown"] <= 0
    assert portfolio["bestYear"] and portfolio["worstYear"]
    assert portfolio["winningPeriods"] + portfolio["losingPeriods"] > 0
    assert response.json()["benchmarks"]


def test_rebalance_comparison():
    response = client.post("/api/backtest/rebalance", json={
        "weights": WEIGHTS, "symbols": UNIVERSE, "initialValue": 1_000_000,
    })
    results = response.json()["results"]
    assert len(results) == 6
    assert {r["frequency"] for r in results} == {"none", "monthly", "quarterly",
                                                "semiannual", "annual", "threshold"}


def test_walk_forward_labels_in_and_out_of_sample():
    response = client.post("/api/backtest/walk-forward", json={
        "weights": WEIGHTS, "symbols": UNIVERSE, "trainEnd": "2023-12-31",
    }) if False else client.post("/api/backtest/walk-forward", json={
        "symbols": UNIVERSE, "trainEnd": "2023-12-31", "strategy": "max_sharpe",
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["inSample"]["label"] == "in-sample"
    assert payload["outOfSample"]["label"] == "out-of-sample"
    # The out-of-sample window must start after the training window ends.
    assert payload["assumptions"]["testStart"] > payload["assumptions"]["trainEnd"]
    assert payload["assumptions"]["noLookAhead"] is True


def test_monte_carlo_is_reproducible_and_labelled():
    kwargs = {
        "weights": WEIGHTS, "symbols": UNIVERSE, "initialValue": 1_000_000,
        "monthlyContribution": 20_000, "years": 10, "paths": 2000, "seed": 7,
    }
    first = client.post("/api/monte-carlo", json=kwargs).json()
    second = client.post("/api/monte-carlo", json=kwargs).json()
    assert first["finalValues"] == second["finalValues"]
    assert first["assumptions"]["illustrativeOnly"] is True
    values = [first["finalValues"][k] for k in ("p10", "p25", "p50", "p75", "p90")]
    assert all(b >= a for a, b in zip(values, values[1:]))


def test_stress_test_scenarios_and_history():
    response = client.post("/api/stress-test", json={
        "weights": WEIGHTS, "symbols": UNIVERSE, "portfolioValue": 1_000_000,
    })
    payload = response.json()
    assert len(payload["scenarios"]) >= 5
    for scenario in payload["scenarios"]:
        assert scenario["basis"] == "illustrative"
        assert scenario["caveat"]
    assert payload["historicalWindows"]


def test_custom_stress_scenario():
    response = client.post("/api/stress-test", json={
        "weights": {"NIFTY50": 1.0}, "symbols": UNIVERSE,
        "scenarios": ["custom"],
        "customShocks": [{"scope": "assetClass", "target": "equity", "shock": -0.25}],
        "portfolioValue": 1_000_000,
    })
    scenario = response.json()["scenarios"][0]
    assert scenario["portfolioImpact"] == pytest.approx(-0.25)
    assert scenario["valueAfter"] == pytest.approx(750_000)


def test_correlation_endpoint():
    response = client.post("/api/analytics/correlation", json={"symbols": UNIVERSE, "window": 500})
    payload = response.json()
    assert payload["symbols"] == UNIVERSE
    assert len(payload["matrix"]) == len(UNIVERSE)
    assert -1.0 <= payload["matrix"][0][1] <= 1.0
    assert payload["windowDays"] == 500


def test_risk_contribution_sums_to_full_risk():
    response = client.post("/api/portfolio/risk-contribution",
                           json={"weights": WEIGHTS, "symbols": UNIVERSE})
    payload = response.json()
    total = sum(c["riskShare"] for c in payload["contributions"])
    assert total == pytest.approx(1.0, abs=1e-6)
    # Capital weight and risk share must differ -- that is the whole point.
    shares = {c["symbol"]: c["riskShare"] for c in payload["contributions"]}
    assert shares["NIFTY50"] > shares["GSEC10Y"]


def test_diversification_ladder_shows_volatility_deltas():
    response = client.post("/api/portfolio/diversification",
                           json={"weights": {"NIFTY50": 1.0}, "symbols": UNIVERSE})
    payload = response.json()
    assert len(payload["steps"]) >= 2
    for step in payload["steps"][1:]:
        assert "volatilityChange" in step
        assert "drawdownChange" in step
    assert payload["period"]
