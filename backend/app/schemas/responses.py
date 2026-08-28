"""Shared response envelopes.

Every analytical response carries: the numbers, the assumptions used, and the
mode / provenance of the underlying data. That is what keeps the system from
becoming a black box (spec section 51).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class DataStatus(BaseModel):
    model_config = ConfigDict(extra="allow")
    mode: str
    provider: str
    lastUpdated: str
    isDemo: bool


class ErrorPayload(BaseModel):
    error: str
    code: str
    suggestions: list[str] = []
    detail: dict[str, Any] | None = None
