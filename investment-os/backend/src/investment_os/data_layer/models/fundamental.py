"""Fundamental snapshot domain model.

Maps 1-to-1 with the `fundamentals` DuckDB table added in Phase 1.

Import path:
    from investment_os.data_layer.models.fundamental import FundamentalSnapshot, PeriodType, FundamentalSource
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class PeriodType(str, Enum):
    QUARTERLY = "quarterly"
    ANNUAL    = "annual"
    TTM       = "ttm"       # trailing twelve months


class FundamentalSource(str, Enum):
    TICKERTAPE = "tickertape"
    YFINANCE   = "yfinance"
    MANUAL     = "manual"


class FundamentalSnapshot(BaseModel):
    """One row of fundamental data for a symbol at a given period-end date.

    All financial figures in ₹ crore unless the field name says otherwise
    (e.g. eps is ₹/share, ratios are unitless, pct fields are percentages).
    """

    id: str
    symbol: str
    period_end: date
    period_type: PeriodType
    source: FundamentalSource

    # ── Income statement ──────────────────────────────────────────────────────
    revenue_cr: Optional[float] = None
    net_profit_cr: Optional[float] = None
    ebitda_cr: Optional[float] = None

    # ── Per-share ─────────────────────────────────────────────────────────────
    eps: Optional[float] = None
    book_value_per_share: Optional[float] = None

    # ── Valuation ratios ──────────────────────────────────────────────────────
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None

    # ── Quality ratios ────────────────────────────────────────────────────────
    roce_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None

    # ── Ownership ────────────────────────────────────────────────────────────
    promoter_holding_pct: Optional[float] = None
    fii_holding_pct: Optional[float] = None

    raw_data: Optional[dict[str, Any]] = None
    fetched_at: datetime = Field(default_factory=datetime.now)

    model_config = {"use_enum_values": True}

    @property
    def is_profitable(self) -> bool:
        return (self.net_profit_cr or 0) > 0

    @property
    def quality_score(self) -> float | None:
        """Simple 0-10 quality proxy from ROCE, ROE, D/E.  None if data missing."""
        if self.roce_pct is None or self.roe_pct is None or self.debt_to_equity is None:
            return None
        # ROCE > 15 = good, ROE > 15 = good, D/E < 1 = good
        score = 0.0
        score += min(self.roce_pct / 15, 1.0) * 4   # max 4 pts
        score += min(self.roe_pct / 15, 1.0) * 3    # max 3 pts
        score += max(0, 1 - self.debt_to_equity) * 3  # max 3 pts
        return round(score, 2)

    def __repr__(self) -> str:  # pragma: no cover
        return f"FundamentalSnapshot({self.symbol!r} {self.period_end} {self.period_type})"
