"""Data-quality pipeline.

Runs *before* any analytics. It never repairs data silently: issues are
reported, affected assets are quarantined with a reason, and the analysis
proceeds only on the surviving set. The UI must surface the score and the
reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = ["QualityReport", "DataQualityIssue", "assess_quality", "min_observations_for"]


@dataclass
class DataQualityIssue:
    code: str
    severity: str          # "info" | "warning" | "critical"
    symbol: str | None
    message: str
    count: int = 0
    penalty: float = 0.0


@dataclass
class QualityReport:
    score: float
    grade: str
    issues: list[DataQualityIssue] = field(default_factory=list)
    usableSymbols: list[str] = field(default_factory=list)
    quarantined: dict[str, list[str]] = field(default_factory=dict)
    symbolScores: dict[str, float] = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "grade": self.grade,
            "issues": [
                {
                    "code": i.code,
                    "severity": i.severity,
                    "symbol": i.symbol,
                    "message": i.message,
                    "count": i.count,
                }
                for i in self.issues
            ],
            "usableSymbols": self.usableSymbols,
            "quarantined": self.quarantined,
            "symbolScores": {k: round(v, 1) for k, v in self.symbolScores.items()},
            "coverage": self.coverage,
        }


def min_observations_for(min_years: float = 3.0, periods_per_year: int = 252) -> int:
    return int(min_years * periods_per_year)


def _grade(score: float) -> str:
    if score >= 95:
        return "Excellent"
    if score >= 85:
        return "Good"
    if score >= 70:
        return "Fair"
    if score >= 50:
        return "Poor"
    return "Unusable"


def assess_quality(
    prices: pd.DataFrame,
    base_currency: str = "INR",
    currencies: dict[str, str] | None = None,
    min_observations: int = 756,
    jump_threshold: float = 0.25,
    max_missing_fraction: float = 0.05,
) -> QualityReport:
    """Score a price frame and quarantine anything that cannot be analysed.

    Checks performed: duplicate dates, unsorted dates, missing prices,
    zero/negative prices, non-finite values, extreme unexplained jumps,
    inconsistent trading calendars, currency mismatches, delisted / short
    history (survivorship) and stale (frozen) prices.
    """
    issues: list[DataQualityIssue] = []
    quarantined: dict[str, list[str]] = {}
    symbol_scores: dict[str, float] = {}

    if prices is None or prices.empty:
        return QualityReport(
            score=0.0,
            grade="Unusable",
            issues=[DataQualityIssue("empty", "critical", None, "No price data was supplied.", 0, 100.0)],
        )

    frame = prices.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        issues.append(DataQualityIssue("bad_index", "critical", None, "Price index is not datetime.", 0, 20.0))

    # ---------------------------------------------------------- index checks
    index = pd.DatetimeIndex(frame.index)
    duplicates = int(index.duplicated().sum())
    if duplicates:
        issues.append(
            DataQualityIssue("duplicate_dates", "critical", None,
                             f"{duplicates} duplicate dates found in the price index.", duplicates, 15.0)
        )
        frame = frame[~frame.index.duplicated(keep="last")]
        index = pd.DatetimeIndex(frame.index)
    if not index.is_monotonic_increasing:
        issues.append(DataQualityIssue("unsorted", "warning", None, "Prices were not sorted by date.", 0, 2.0))
        frame = frame.sort_index()
        index = pd.DatetimeIndex(frame.index)

    expected = pd.bdate_range(index[0], index[-1])
    missing_sessions = len(set(expected) - set(index))
    if missing_sessions > max(5, 0.02 * len(expected)):
        issues.append(
            DataQualityIssue("calendar_gaps", "warning", None,
                             f"{missing_sessions} expected trading sessions are absent from the series.",
                             missing_sessions, 5.0)
        )

    total_cells = int(frame.size)
    symbol_penalties: dict[str, float] = {}

    for symbol in frame.columns:
        reasons: list[str] = []
        series = pd.to_numeric(frame[symbol], errors="coerce")

        missing = int(series.isna().sum())
        if missing:
            fraction = missing / max(len(series), 1)
            reasons.append(f"{missing} missing prices ({fraction:.1%})")
            if fraction > max_missing_fraction:
                issues.append(
                    DataQualityIssue("missing_prices", "critical", symbol,
                                     f"{symbol}: {missing} missing prices ({fraction:.1%} of the series).",
                                     missing, 10.0)
                )
                symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 25.0

        finite = series.dropna()
        non_positive = int((finite <= 0).sum())
        if non_positive:
            reasons.append(f"{non_positive} zero or negative prices")
            issues.append(
                DataQualityIssue("non_positive_price", "critical", symbol,
                                 f"{symbol}: {non_positive} zero or negative prices.", non_positive, 10.0)
            )
            symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 30.0

        observations = int(finite.size)
        if observations < min_observations:
            reasons.append(f"only {observations} observations (minimum {min_observations})")
            issues.append(
                DataQualityIssue("insufficient_history", "critical", symbol,
                                 f"{symbol}: {observations} observations, fewer than the {min_observations} "
                                 "required for this analysis.", observations, 10.0)
            )
            symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 40.0

        if observations >= 30:
            rets = finite.pct_change().dropna()
            extreme = int((rets.abs() > jump_threshold).sum())
            if extreme:
                reasons.append(f"{extreme} daily moves above {jump_threshold:.0%}")
                issues.append(
                    DataQualityIssue("extreme_jump", "warning", symbol,
                                     f"{symbol}: {extreme} daily moves exceed {jump_threshold:.0%} "
                                     "(possible corporate action or data error).", extreme, 3.0)
                )
                symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 3.0
            stale = int((rets.abs() < 1e-12).sum())
            if stale > 0.25 * max(len(rets), 1):
                reasons.append(f"{stale} unchanged prices (stale feed)")
                issues.append(
                    DataQualityIssue("stale_prices", "warning", symbol,
                                     f"{symbol}: {stale} consecutive unchanged prices.", stale, 3.0)
                )
                symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 5.0

        # Trading-calendar consistency: an asset that covers far fewer sessions
        # than the universe has a different calendar or was listed late.
        coverage = observations / max(len(frame), 1)
        if coverage < 0.9:
            reasons.append(f"covers only {coverage:.0%} of the universe sessions")
            issues.append(
                DataQualityIssue("calendar_mismatch", "warning", symbol,
                                 f"{symbol}: present on only {coverage:.0%} of sessions "
                                 "(different calendar, late listing or delisting).", 0, 2.0)
            )
            symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 8.0

        if currencies and currencies.get(symbol, base_currency) != base_currency:
            issues.append(
                DataQualityIssue("currency_mismatch", "critical", symbol,
                                 f"{symbol}: quoted in {currencies.get(symbol)} but the base currency is "
                                 f"{base_currency}. No FX conversion was applied.", 0, 10.0)
            )
            symbol_penalties[symbol] = symbol_penalties.get(symbol, 0.0) + 40.0
            reasons.append("currency mismatch")

        # First/last observation gaps are a survivorship / delisting signal.
        first_valid = series.first_valid_index()
        last_valid = series.last_valid_index()
        if first_valid is not None and first_valid > frame.index[int(0.1 * len(frame))]:
            issues.append(
                DataQualityIssue("late_history_start", "info", symbol,
                                 f"{symbol}: history begins {pd.Timestamp(first_valid).date()}, after the "
                                 "start of the sample (possible survivorship bias).", 0, 1.0)
            )
        if last_valid is not None and last_valid < frame.index[int(0.98 * (len(frame) - 1))]:
            issues.append(
                DataQualityIssue("early_history_end", "warning", symbol,
                                 f"{symbol}: history ends {pd.Timestamp(last_valid).date()}, before the end "
                                 "of the sample (possible delisting).", 0, 4.0)
            )
            reasons.append("series ends before the sample end")

        symbol_scores[symbol] = float(max(0.0, 100.0 - symbol_penalties.get(symbol, 0.0)))
        if reasons:
            quarantined[symbol] = reasons

    # Universe-level score: base 100 less per-issue penalties, scaled by how
    # much of the data is affected.
    penalty = sum(i.penalty for i in issues if i.severity == "critical")
    penalty += 0.5 * sum(i.penalty for i in issues if i.severity == "warning")
    penalty += 0.1 * sum(i.penalty for i in issues if i.severity == "info")
    score = float(max(0.0, 100.0 - penalty))

    usable = [s for s in frame.columns if not _is_blocking(quarantined.get(s, []), s, symbol_scores, min_observations, frame)]
    coverage = {
        "start": str(frame.index[0].date()),
        "end": str(frame.index[-1].date()),
        "sessions": int(len(frame)),
        "symbols": int(frame.shape[1]),
        "usableSymbols": len(usable),
        "missingCells": int(frame.isna().sum().sum()),
        "totalCells": total_cells,
    }
    return QualityReport(
        score=score,
        grade=_grade(score),
        issues=issues,
        usableSymbols=usable,
        quarantined=quarantined,
        symbolScores=symbol_scores,
        coverage=coverage,
    )


def _is_blocking(reasons: list[str], symbol: str, scores: dict[str, float], min_obs: int, frame: pd.DataFrame) -> bool:
    """An asset is blocked when its data is structurally unusable or too short."""
    blocking_keys = ("zero or negative prices", "currency mismatch", "only ")
    return any(any(key in r for key in blocking_keys) for r in reasons)
