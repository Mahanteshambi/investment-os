"""Screener export domain model.

Maps 1-to-1 with the `screener_exports` DuckDB table.  Represents one row
from a Tickertape Pro or Screener.in CSV export.

Import path:
    from investment_os.data_layer.models.screener import ScreenerRow, ScreenerSource
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ScreenerSource(str, Enum):
    TICKERTAPE = "tickertape"
    SCREENER_IN = "screener_in"
    MANUAL = "manual"


class ScreenerRow(BaseModel):
    """One instrument row from a screener CSV export.

    Raw CSV data is preserved in `raw_row` so the row can be re-processed
    if column mapping logic changes.
    """

    id: str
    source: ScreenerSource
    symbol: str
    export_date: date

    # ── Identity ──────────────────────────────────────────────────────────────
    company_name: Optional[str] = None
    sector: Optional[str] = None

    # ── Size ──────────────────────────────────────────────────────────────────
    market_cap_cr: Optional[float] = None

    # ── Valuation ─────────────────────────────────────────────────────────────
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None

    # ── Quality ───────────────────────────────────────────────────────────────
    roce_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None

    # ── Growth ────────────────────────────────────────────────────────────────
    revenue_growth_1y: Optional[float] = None
    profit_growth_1y: Optional[float] = None

    # ── Income ────────────────────────────────────────────────────────────────
    dividend_yield_pct: Optional[float] = None

    # ── Screener composite score (if the export includes one) ─────────────────
    score_raw: Optional[float] = None

    # ── Audit ────────────────────────────────────────────────────────────────
    raw_row: Optional[dict[str, Any]] = None
    imported_at: datetime = Field(default_factory=datetime.now)

    model_config = {"use_enum_values": True}

    @property
    def is_large_cap(self) -> bool:
        return (self.market_cap_cr or 0) >= 20_000  # ₹20,000 Cr+

    @property
    def is_mid_cap(self) -> bool:
        cap = self.market_cap_cr or 0
        return 5_000 <= cap < 20_000

    def __repr__(self) -> str:  # pragma: no cover
        return f"ScreenerRow({self.symbol!r} {self.export_date} src={self.source})"
