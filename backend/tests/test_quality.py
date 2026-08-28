import numpy as np
import pandas as pd
import pytest

from app.data.quality import assess_quality


def _clean_frame(days=800, cols=("A", "B")):
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2018-01-01", periods=days)
    data = {c: 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, days)) for c in cols}
    return pd.DataFrame(data, index=dates)


def test_clean_data_scores_highly():
    report = assess_quality(_clean_frame())
    assert report.score >= 95
    assert report.grade == "Excellent"
    assert set(report.usableSymbols) == {"A", "B"}


def test_negative_prices_are_quarantined():
    frame = _clean_frame()
    frame.loc[frame.index[10], "A"] = -5.0
    report = assess_quality(frame)
    assert "A" in report.quarantined
    assert any(i.code == "non_positive_price" for i in report.issues)
    assert "A" not in report.usableSymbols


def test_zero_prices_are_rejected():
    frame = _clean_frame()
    frame.loc[frame.index[5], "B"] = 0.0
    report = assess_quality(frame)
    assert any("zero or negative" in r for r in report.quarantined["B"])


def test_duplicate_dates_are_detected():
    frame = _clean_frame()
    dup = frame.iloc[[3]]
    frame = pd.concat([frame, dup]).sort_index()
    report = assess_quality(frame)
    assert any(i.code == "duplicate_dates" for i in report.issues)


def test_insufficient_history_is_reported():
    report = assess_quality(_clean_frame(days=10), min_observations=756)
    assert any(i.code == "insufficient_history" for i in report.issues)
    assert report.usableSymbols == []


def test_missing_prices_are_reported_not_filled():
    frame = _clean_frame()
    frame.iloc[100:200, 0] = np.nan
    report = assess_quality(frame)
    assert any(i.code == "missing_prices" for i in report.issues)
    # The pipeline must NOT have filled anything in.
    assert frame.iloc[100, 0] != frame.iloc[100, 0]  # still NaN


def test_extreme_jumps_are_flagged():
    frame = _clean_frame()
    frame.iloc[500, 0] = frame.iloc[499, 0] * 2.5  # +150% in one day
    report = assess_quality(frame)
    assert any(i.code == "extreme_jump" for i in report.issues)


def test_currency_mismatch_is_blocking():
    frame = _clean_frame()
    report = assess_quality(frame, base_currency="INR", currencies={"A": "USD", "B": "INR"})
    assert any(i.code == "currency_mismatch" for i in report.issues)
    assert "A" not in report.usableSymbols


def test_empty_frame_is_unusable():
    report = assess_quality(pd.DataFrame())
    assert report.grade == "Unusable"
    assert report.score == 0.0


def test_report_serialises():
    payload = assess_quality(_clean_frame()).as_dict()
    assert "score" in payload and "grade" in payload and "coverage" in payload
    assert isinstance(payload["issues"], list)
