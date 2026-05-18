"""Canonical price domain models.

OHLCBar is defined here and imported by both kite_client and yfinance_client,
eliminating the duplication that existed in Phase 1.

Import path:
    from investment_os.data_layer.models.price import OHLCBar, PriceHistory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd  # optional — only used in as_dataframe()


@dataclass(slots=True)
class OHLCBar:
    """Single OHLCV candle — source-agnostic (Kite or yfinance)."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    symbol: str = ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"OHLCBar({self.date} C={self.close:.2f} sym={self.symbol!r})"

    @classmethod
    def from_kite_candle(cls, candle: dict, symbol: str = "") -> "OHLCBar":
        """Construct from a raw kiteconnect historical_data dict."""
        raw_date = candle["date"]
        bar_date = (
            raw_date.date()
            if isinstance(raw_date, datetime)
            else date.fromisoformat(str(raw_date)[:10])
        )
        return cls(
            date=bar_date,
            open=float(candle.get("open", 0)),
            high=float(candle.get("high", 0)),
            low=float(candle.get("low", 0)),
            close=float(candle.get("close", 0)),
            volume=int(candle.get("volume", 0)),
            symbol=symbol,
        )

    @classmethod
    def from_yfinance_row(cls, idx, row, symbol: str = "") -> "OHLCBar":
        """Construct from a pandas DataFrame row produced by yfinance.download()."""
        bar_date = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
        return cls(
            date=bar_date,
            open=float(row.get("Open", 0)),
            high=float(row.get("High", 0)),
            low=float(row.get("Low", 0)),
            close=float(row.get("Close", 0)),
            volume=int(row.get("Volume", 0)),
            symbol=symbol,
        )


@dataclass
class PriceHistory:
    """Ordered collection of OHLCBars for a single symbol.

    Bars are stored oldest-first (same order returned by Kite and yfinance).
    """

    symbol: str
    bars: list[OHLCBar] = field(default_factory=list)

    # ── Convenience accessors ─────────────────────────────────────────────────

    @property
    def latest(self) -> OHLCBar | None:
        """Most recent bar, or None if empty."""
        return self.bars[-1] if self.bars else None

    @property
    def latest_close(self) -> float | None:
        return self.latest.close if self.latest else None

    @property
    def latest_date(self) -> date | None:
        return self.latest.date if self.latest else None

    def closes(self) -> list[float]:
        """Return all closing prices oldest-first."""
        return [b.close for b in self.bars]

    def pct_change(self, days: int = 1) -> float | None:
        """Percentage change over the last `days` bars.  None if insufficient data."""
        if len(self.bars) < days + 1:
            return None
        old = self.bars[-(days + 1)].close
        new = self.bars[-1].close
        return ((new - old) / old * 100) if old else None

    def as_dataframe(self) -> "pd.DataFrame":
        """Convert to a pandas DataFrame indexed by date."""
        import pandas as pd  # noqa: PLC0415

        if not self.bars:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        return pd.DataFrame(
            [
                {
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in self.bars
            ]
        ).set_index("date")

    def __len__(self) -> int:
        return len(self.bars)

    def __repr__(self) -> str:  # pragma: no cover
        return f"PriceHistory({self.symbol!r}, {len(self.bars)} bars)"
