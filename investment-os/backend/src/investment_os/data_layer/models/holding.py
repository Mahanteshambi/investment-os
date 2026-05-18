"""Holding domain model.

Maps 1-to-1 with the `holdings` DuckDB table.  Used by HoldingsRepository
and any service that needs to reason about the portfolio.

Import path:
    from investment_os.data_layer.models.holding import Holding, AssetClass, HoldingSource
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AssetClass(str, Enum):
    EQUITY   = "equity"
    ETF      = "etf"
    MF       = "mf"
    GOLD     = "gold"
    CASH     = "cash"
    DEBT     = "debt"
    FD       = "fd"
    PF       = "pf"     # Provident Fund
    PPF      = "ppf"    # Public Provident Fund
    SAVINGS  = "savings"


class SubClass(str, Enum):
    LARGE_CAP     = "large_cap"
    MID_SMALL_CAP = "mid_small_cap"
    GOLD_ETF      = "gold_etf"
    LIQUID        = "liquid"
    INTERNATIONAL = "international"
    SECTOR        = "sector"


class HoldingSource(str, Enum):
    KITE   = "kite"
    SHEETS = "sheets"
    MANUAL = "manual"


class Holding(BaseModel):
    """Domain model for a single portfolio holding.

    Field names match the `holdings` table columns exactly so repositories
    can use model_dump() directly for inserts.
    """

    id: str
    asset_name: str
    ticker: Optional[str] = None
    asset_class: AssetClass
    sub_class: Optional[str] = None
    source: HoldingSource
    platform: Optional[str] = None

    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    current_value: float = 0.0
    invested_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    sector: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.now)

    model_config = {"use_enum_values": True}

    @model_validator(mode="after")
    def _compute_derived(self) -> "Holding":
        """Back-fill computed fields if caller only supplied raw inputs."""
        if self.current_value == 0 and self.quantity and self.current_price:
            self.current_value = round(self.quantity * self.current_price, 4)
        if self.invested_value == 0 and self.quantity and self.avg_cost:
            self.invested_value = round(self.quantity * self.avg_cost, 4)
        if self.unrealized_pnl == 0 and self.current_value and self.invested_value:
            self.unrealized_pnl = round(self.current_value - self.invested_value, 4)
        if self.unrealized_pnl_pct == 0 and self.invested_value:
            self.unrealized_pnl_pct = round(self.unrealized_pnl / self.invested_value * 100, 4)
        return self

    @property
    def is_profitable(self) -> bool:
        return self.unrealized_pnl > 0

    @property
    def gain_pct(self) -> float:
        return self.unrealized_pnl_pct

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Holding({self.ticker or self.asset_name!r} "
            f"qty={self.quantity} pnl={self.unrealized_pnl_pct:.1f}%)"
        )
