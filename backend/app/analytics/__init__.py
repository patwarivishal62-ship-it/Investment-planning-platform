"""Analytics package: pure, deterministic, side-effect-free maths.

No module here performs I/O, reads configuration globals, or knows about the
web layer. Every financial assumption (risk-free rate, periods per year,
confidence level, ...) is passed in explicitly so results are reproducible
and unit-testable.
"""
