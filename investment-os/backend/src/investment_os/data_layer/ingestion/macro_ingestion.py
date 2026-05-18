"""Macro indicator ingestion pipeline.

Fetches DXY, US 10-year yield, and Brent crude from Yahoo Finance via
YfinanceClient and writes them to the existing `macro_data` DuckDB table.

The `macro_data` table has a (date, metric) PRIMARY KEY so all writes are
naturally idempotent — re-running on the same day is safe.

Usage:
    from investment_os.data_layer.ingestion.macro_ingestion import MacroIngestion

    result = MacroIngestion().run()
    print(result.summary())

    # Or fetch a single metric:
    result = MacroIngestion().run(metrics=["DXY"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.clients.yfinance_client import MacroDataPoint, YfinanceClient
from investment_os.data_layer.db import get_cursor

logger = get_logger(__name__)

# Canonical metric names — must match MACRO_TICKERS keys in yfinance_client
DEFAULT_METRICS: list[str] = ["DXY", "US10Y", "BRENT"]

_UPSERT_SQL = """
    INSERT INTO macro_data (date, metric, value)
    VALUES (?, ?, ?)
    ON CONFLICT (date, metric) DO UPDATE SET value = excluded.value
"""


@dataclass
class MacroIngestionResult:
    metrics: list[str] = field(default_factory=list)
    points_submitted: int = 0
    latest_values: dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        vals = "  ".join(f"{k}={v:.2f}" for k, v in self.latest_values.items())
        status = "OK" if self.ok else f"ERROR: {self.error}"
        return f"Macro ingestion [{status}]: {self.points_submitted} points — {vals}"


class MacroIngestion:
    """Fetches macro data from Yahoo Finance and persists to `macro_data` table."""

    def __init__(
        self,
        yf_client: Optional[YfinanceClient] = None,
        lookback_days: int = 7,
    ) -> None:
        self._yf = yf_client or YfinanceClient()
        self._lookback_days = lookback_days

    def run(self, metrics: Optional[list[str]] = None) -> MacroIngestionResult:
        """Fetch and persist macro indicators.

        Args:
            metrics: Subset of metric names to fetch (default: DXY, US10Y, BRENT).

        Returns:
            MacroIngestionResult with counts and latest values.
        """
        target_metrics = metrics or DEFAULT_METRICS
        logger.info("Macro ingestion: %s", target_metrics)

        try:
            points: list[MacroDataPoint] = self._yf.get_macro_data(
                metrics=target_metrics,
                days=self._lookback_days,
            )
        except Exception as exc:
            logger.error("Failed to fetch macro data: %s", exc)
            return MacroIngestionResult(metrics=target_metrics, error=str(exc))

        if not points:
            logger.warning("No macro data returned for %s", target_metrics)
            return MacroIngestionResult(metrics=target_metrics, points_submitted=0)

        # Persist to DuckDB
        rows = [(p.date, p.metric, p.value) for p in points]
        try:
            with get_cursor() as cur:
                cur.executemany(_UPSERT_SQL, rows)
            logger.info("Macro: %d data points upserted", len(rows))
        except Exception as exc:
            logger.error("macro_data upsert failed: %s", exc)
            return MacroIngestionResult(metrics=target_metrics, error=str(exc))

        # Compute latest value per metric for the result summary
        latest: dict[str, float] = {}
        for p in points:
            latest[p.metric] = p.value  # last iteration = most recent

        return MacroIngestionResult(
            metrics=target_metrics,
            points_submitted=len(rows),
            latest_values=latest,
        )

    def get_latest_from_db(self, metrics: Optional[list[str]] = None) -> dict[str, float]:
        """Read the most recent value per metric directly from `macro_data`.

        Useful for analysis tools that need current macro state without
        triggering a fresh network fetch.

        Returns:
            e.g. {"DXY": 104.23, "US10Y": 4.51, "BRENT": 83.12}
        """
        target = metrics or DEFAULT_METRICS
        placeholders = ", ".join("?" * len(target))
        sql = f"""
            SELECT metric, value
            FROM (
                SELECT metric, value,
                       ROW_NUMBER() OVER (PARTITION BY metric ORDER BY date DESC) AS rn
                FROM macro_data
                WHERE metric IN ({placeholders})
            )
            WHERE rn = 1
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, target).fetchall()

        result = {r[0]: float(r[1]) for r in rows}
        logger.debug("Latest macro from DB: %s", result)
        return result

    def get_history_from_db(
        self,
        metric: str,
        days: int = 30,
    ) -> list[tuple[date, float]]:
        """Return (date, value) pairs for a metric over the last N days.

        Useful for trend analysis in Phase 4 scoring.
        """
        sql = """
            SELECT date, value
            FROM macro_data
            WHERE metric = ?
              AND date >= CURRENT_DATE - INTERVAL (? || ' days')
            ORDER BY date ASC
        """
        with get_cursor() as cur:
            rows = cur.execute(sql, [metric, days]).fetchall()

        return [
            (r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0])), float(r[1]))
            for r in rows
        ]
