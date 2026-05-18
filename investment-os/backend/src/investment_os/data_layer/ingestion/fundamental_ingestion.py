"""Fundamental data ingestion from Tickertape Pro CSV exports.

Parses a Tickertape CSV, writes both:
  - ScreenerRow objects → screener_exports table
  - FundamentalSnapshot objects → fundamentals table

Both writes are idempotent (ON CONFLICT DO NOTHING), so re-running with the
same file is safe.

Usage:
    from investment_os.data_layer.ingestion.fundamental_ingestion import FundamentalIngestion

    result = FundamentalIngestion().run("/path/to/tickertape_export.csv")
    print(result.summary())
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.loaders.tickertape_loader import TickertapeLoader
from investment_os.data_layer.models.fundamental import FundamentalSource, PeriodType
from investment_os.data_layer.models.screener import ScreenerSource
from investment_os.data_layer.repositories.fundamentals_repository import FundamentalsRepository
from investment_os.data_layer.repositories.screener_repository import ScreenerRepository

logger = get_logger(__name__)


@dataclass
class FundamentalIngestionResult:
    csv_path: str
    export_date: date
    screener_rows_submitted: int = 0
    fundamental_snaps_submitted: int = 0
    skipped_symbols: list[str] = None  # type: ignore[assignment]
    error: Optional[str] = None

    def __post_init__(self):
        if self.skipped_symbols is None:
            self.skipped_symbols = []

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        return (
            f"Fundamental ingestion from {Path(self.csv_path).name} "
            f"(date={self.export_date}): "
            f"{self.screener_rows_submitted} screener rows, "
            f"{self.fundamental_snaps_submitted} fundamental snapshots submitted"
            + (f" — ERROR: {self.error}" if self.error else "")
        )


class FundamentalIngestion:
    """Orchestrates Tickertape CSV → DuckDB (screener_exports + fundamentals)."""

    def __init__(
        self,
        screener_repo: Optional[ScreenerRepository] = None,
        fundamentals_repo: Optional[FundamentalsRepository] = None,
        loader: Optional[TickertapeLoader] = None,
    ) -> None:
        self._screener_repo = screener_repo or ScreenerRepository()
        self._fundamentals_repo = fundamentals_repo or FundamentalsRepository()
        self._loader = loader or TickertapeLoader()

    def run(
        self,
        csv_path: str | Path,
        export_date: Optional[date] = None,
        source: ScreenerSource = ScreenerSource.TICKERTAPE,
        period_type: PeriodType = PeriodType.TTM,
    ) -> FundamentalIngestionResult:
        """Parse a Tickertape CSV and persist results to DuckDB.

        Args:
            csv_path:    Path to the Tickertape Pro export CSV.
            export_date: Override the export date (defaults to file mtime).
            source:      ScreenerSource tag for all rows.
            period_type: PeriodType applied to FundamentalSnapshot rows.

        Returns:
            FundamentalIngestionResult with submission counts.
        """
        path = Path(csv_path)
        logger.info("Fundamental ingestion: %s", path.name)

        try:
            screener_rows, fundamental_snaps = self._loader.load(
                path,
                export_date=export_date,
                source=source,
                period_type=period_type,
            )
        except Exception as exc:
            logger.error("Failed to parse CSV %s: %s", path, exc)
            return FundamentalIngestionResult(
                csv_path=str(path),
                export_date=export_date or date.today(),
                error=str(exc),
            )

        exp_date = export_date or (screener_rows[0].export_date if screener_rows else date.today())

        # ── Persist screener rows ─────────────────────────────────────────────
        screener_inserted = 0
        if screener_rows:
            try:
                screener_inserted = self._screener_repo.bulk_insert(screener_rows)
                logger.info("Screener: %d rows submitted", screener_inserted)
            except Exception as exc:
                logger.error("Screener bulk_insert failed: %s", exc)

        # ── Persist fundamental snapshots ─────────────────────────────────────
        fundamental_inserted = 0
        skipped: list[str] = []
        if fundamental_snaps:
            # Filter out snapshots with no useful data (all None ratios)
            useful = [
                s for s in fundamental_snaps
                if any(v is not None for v in [
                    s.pe_ratio, s.pb_ratio, s.roce_pct, s.roe_pct,
                    s.debt_to_equity, s.revenue_growth_1y, s.profit_growth_1y,
                ])
            ]
            skipped = [s.symbol for s in fundamental_snaps if s not in useful]
            try:
                fundamental_inserted = self._fundamentals_repo.bulk_upsert(useful)
                logger.info("Fundamentals: %d snapshots submitted (%d skipped — no data)", fundamental_inserted, len(skipped))
            except Exception as exc:
                logger.error("Fundamentals bulk_upsert failed: %s", exc)

        return FundamentalIngestionResult(
            csv_path=str(path),
            export_date=exp_date,
            screener_rows_submitted=screener_inserted,
            fundamental_snaps_submitted=fundamental_inserted,
            skipped_symbols=skipped,
        )

    def run_directory(
        self,
        directory: str | Path,
        pattern: str = "*.csv",
        source: ScreenerSource = ScreenerSource.TICKERTAPE,
    ) -> list[FundamentalIngestionResult]:
        """Process all CSVs in a directory matching `pattern`.

        Files are processed oldest-first (by filename, assuming YYYY-MM-DD prefix).
        Already-processed rows are skipped by the ON CONFLICT constraint.
        """
        dir_path = Path(directory)
        csv_files = sorted(dir_path.glob(pattern))
        logger.info("run_directory: found %d CSVs in %s", len(csv_files), dir_path)

        results: list[FundamentalIngestionResult] = []
        for csv_file in csv_files:
            result = self.run(csv_file, source=source)
            results.append(result)
            logger.info(result.summary())

        return results
