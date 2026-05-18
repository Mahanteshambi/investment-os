"""yfinance client for the Investment OS data layer.

Responsibilities:
  1. OHLCV fallback — when Kite token is unavailable or an instrument is
     not in Kite's universe (e.g. mutual funds, US stocks).
  2. Macro data — DXY (DX-Y.NYB), US 10-yr yield (^TNX), Brent crude (BZ=F).

All methods return typed domain objects so the rest of the data layer never
imports yfinance directly.

Import path:
    from investment_os.data_layer.clients.yfinance_client import YfinanceClient
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from investment_os.core.logging import get_logger
from investment_os.data_layer.models.price import OHLCBar  # canonical — no local copy

logger = get_logger(__name__)


# ── Domain types ──────────────────────────────────────────────────────────────

@dataclass(slots=True)
class MacroDataPoint:
    """Single macro indicator value."""
    metric: str          # e.g. "DXY", "US10Y", "BRENT"
    date: date
    value: float


# ── Ticker mapping ────────────────────────────────────────────────────────────

# Maps Investment OS symbols → Yahoo Finance tickers
_NSE_SUFFIX = ".NS"

MACRO_TICKERS: dict[str, str] = {
    "DXY":    "DX-Y.NYB",
    "US10Y":  "^TNX",
    "BRENT":  "BZ=F",
    "GOLD":   "GC=F",
    "NIFTY":  "^NSEI",
}


def nse_ticker(symbol: str) -> str:
    """Convert a bare NSE symbol to a Yahoo Finance ticker (SYMBOL.NS)."""
    s = symbol.upper().strip()
    return s if s.endswith(_NSE_SUFFIX) else f"{s}{_NSE_SUFFIX}"


# ── Client ────────────────────────────────────────────────────────────────────

class YfinanceClient:
    """Thin, typed wrapper around yfinance.

    All network calls are isolated here so the rest of the codebase has
    a single seam to mock in tests.
    """

    # ── OHLCV ─────────────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        ticker: str,
        days: int = 30,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[OHLCBar]:
        """Fetch OHLCV bars for any Yahoo Finance ticker.

        Args:
            ticker: Yahoo Finance ticker symbol (e.g. "NIFTYBEES.NS", "DX-Y.NYB").
            days:   Number of calendar days to look back (ignored when start/end given).
            start:  Explicit start date (inclusive).
            end:    Explicit end date (inclusive, defaults to today).

        Returns:
            List of OHLCBar sorted oldest-first.  Empty list on failure.
        """
        try:
            import yfinance as yf  # type: ignore[import-untyped]
            import pandas as pd    # noqa: F401 — ensure pandas is available
        except ImportError as exc:
            raise RuntimeError("yfinance and pandas are required") from exc

        end_dt = end or date.today()
        start_dt = start or (end_dt - timedelta(days=days))

        logger.debug("yfinance fetch: %s  %s → %s", ticker, start_dt, end_dt)
        try:
            hist = yf.download(
                ticker,
                start=start_dt.isoformat(),
                # yfinance end is exclusive, so add 1 day
                end=(end_dt + timedelta(days=1)).isoformat(),
                auto_adjust=True,
                progress=False,
            )
            # yfinance ≥0.2.x returns MultiLevel columns when downloading a
            # single ticker; flatten to plain column names if that's the case.
            if hasattr(hist.columns, "levels"):
                hist.columns = hist.columns.get_level_values(0)
        except Exception as exc:
            logger.error("yfinance download failed for %s: %s", ticker, exc)
            return []

        if hist is None or hist.empty:
            logger.warning("yfinance returned no data for %s", ticker)
            return []

        bars: list[OHLCBar] = []
        for idx, row in hist.iterrows():
            bars.append(OHLCBar.from_yfinance_row(idx, row, symbol=ticker))

        logger.info("yfinance: fetched %d bars for %s", len(bars), ticker)
        return bars

    def get_nse_ohlcv(self, symbol: str, days: int = 30) -> list[OHLCBar]:
        """Convenience wrapper: fetch OHLCV for an NSE symbol (auto-appends .NS)."""
        return self.get_ohlcv(nse_ticker(symbol), days=days)

    # ── Macro data ────────────────────────────────────────────────────────────

    def get_macro_data(
        self,
        metrics: list[str] | None = None,
        days: int = 5,
    ) -> list[MacroDataPoint]:
        """Fetch latest values for macro indicators.

        Args:
            metrics: Subset of MACRO_TICKERS keys to fetch
                     (default: DXY, US10Y, BRENT).
            days:    Look-back window in calendar days.

        Returns:
            List of MacroDataPoint — one per metric per trading day.
        """
        if metrics is None:
            metrics = ["DXY", "US10Y", "BRENT"]

        results: list[MacroDataPoint] = []
        for metric in metrics:
            yf_ticker = MACRO_TICKERS.get(metric)
            if not yf_ticker:
                logger.warning("Unknown macro metric: %s — skipping", metric)
                continue
            bars = self.get_ohlcv(yf_ticker, days=days)
            for bar in bars:
                results.append(
                    MacroDataPoint(metric=metric, date=bar.date, value=bar.close)
                )

        logger.info(
            "Macro fetch complete: %d data points for %s",
            len(results), metrics,
        )
        return results

    def get_latest_macro(self, metrics: list[str] | None = None) -> dict[str, float]:
        """Return the most recent value for each macro metric as a simple dict.

        Example: {"DXY": 104.23, "US10Y": 4.51, "BRENT": 83.12}
        """
        if metrics is None:
            metrics = ["DXY", "US10Y", "BRENT"]

        points = self.get_macro_data(metrics=metrics, days=7)
        latest: dict[str, float] = {}
        for p in points:
            # Iterating oldest→newest; last write wins → most recent
            latest[p.metric] = p.value
        return latest

    # ── Instrument info ───────────────────────────────────────────────────────

    def get_current_price(self, ticker: str) -> float | None:
        """Return the latest close price for a ticker, or None on failure."""
        bars = self.get_ohlcv(ticker, days=3)
        return bars[-1].close if bars else None

    def get_info(self, ticker: str) -> dict[str, Any]:
        """Return yfinance Ticker.info dict (fundamentals, company metadata).

        Returns an empty dict on failure — callers must handle missing keys.
        """
        try:
            import yfinance as yf  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("yfinance is required") from exc

        try:
            info = yf.Ticker(ticker).info
            return info if isinstance(info, dict) else {}
        except Exception as exc:
            logger.warning("yfinance .info failed for %s: %s", ticker, exc)
            return {}
