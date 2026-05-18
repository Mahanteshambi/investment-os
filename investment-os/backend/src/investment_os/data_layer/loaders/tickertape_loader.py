"""Tickertape Pro CSV loader.

Parses a Tickertape Pro screener export (CSV) and returns typed ScreenerRow
objects ready for the ScreenerRepository.  Also extracts a FundamentalSnapshot
per row for the FundamentalsRepository.

Tickertape column names are inconsistent across export types (Screener, Compare,
Portfolio).  This loader normalises them via a flexible alias map so new column
names can be added without changing repository code.

Usage:
    from investment_os.data_layer.loaders.tickertape_loader import TickertapeLoader

    loader = TickertapeLoader()
    rows, snaps = loader.load("/path/to/export.csv", export_date=date.today())
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.models.fundamental import FundamentalSnapshot, FundamentalSource, PeriodType
from investment_os.data_layer.models.screener import ScreenerRow, ScreenerSource

logger = get_logger(__name__)

# ── Column alias map ──────────────────────────────────────────────────────────
# Maps canonical field names → list of possible Tickertape CSV column headers.
# Case-insensitive matching is applied at load time.

_COLUMN_ALIASES: dict[str, list[str]] = {
    "symbol": [
        "symbol", "nse symbol", "ticker", "nse_symbol", "bse symbol",
    ],
    "company_name": [
        "name", "company name", "company", "company_name", "stock name",
    ],
    "sector": [
        "sector", "industry", "sector name",
    ],
    "market_cap_cr": [
        "market cap", "market cap (cr)", "mcap", "market cap (₹ cr)", "mktcap",
        "market capitalisation", "market cap cr", "market cap(cr.)",
    ],
    "pe_ratio": [
        "pe", "p/e", "pe ratio", "price to earnings", "trailing pe", "pe (ttm)",
    ],
    "pb_ratio": [
        "pb", "p/b", "pb ratio", "price to book", "price/book",
    ],
    "roce_pct": [
        "roce", "roce (%)", "return on capital employed", "roce (ttm)", "roce%",
    ],
    "roe_pct": [
        "roe", "roe (%)", "return on equity", "roe (ttm)", "roe%",
    ],
    "debt_to_equity": [
        "d/e", "debt/equity", "debt to equity", "de ratio", "d/e ratio",
    ],
    "revenue_growth_1y": [
        "revenue growth", "revenue growth (1y)", "rev growth 1y", "sales growth 1y",
        "revenue growth (ttm)", "revenue growth yoy",
    ],
    "profit_growth_1y": [
        "profit growth", "profit growth (1y)", "pat growth 1y", "net profit growth 1y",
        "profit growth (ttm)", "profit growth yoy", "earnings growth 1y",
    ],
    "dividend_yield_pct": [
        "dividend yield", "div yield", "div yield (%)", "dividend yield (%)",
    ],
    "score_raw": [
        "score", "tickertape score", "tt score", "composite score",
    ],
    # Fundamental extras
    "eps": ["eps", "eps (ttm)", "earnings per share"],
    "book_value_per_share": ["book value", "bvps", "book value per share"],
}


def _build_alias_lookup(df_columns: list[str]) -> dict[str, str]:
    """Return {canonical_name: actual_df_column} for whatever columns exist."""
    col_lower = {c.lower().strip(): c for c in df_columns}
    result: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in col_lower:
                result[canonical] = col_lower[alias.lower()]
                break
    return result


def _get(row, alias_map: dict[str, str], field: str):
    col = alias_map.get(field)
    if col is None:
        return None
    v = row.get(col)
    return None if (v is None or str(v).strip() in ("", "-", "N/A", "nan", "NaN")) else v


def _f(v) -> Optional[float]:
    if v is None:
        return None
    try:
        # Handle values like "12.5%" → 12.5 or "1,234.5" → 1234.5
        s = str(v).replace(",", "").replace("%", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return None


def _clean_symbol(raw: str) -> str:
    """Strip exchange prefix (NSE:, BSE:) and whitespace."""
    s = str(raw).strip().upper()
    for prefix in ("NSE:", "BSE:"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


# ── Loader ────────────────────────────────────────────────────────────────────

class TickertapeLoader:
    """Parse a Tickertape Pro CSV export into typed domain objects.

    Supports both Screener exports and Compare-view exports.
    Unknown columns are silently ignored; missing canonical columns produce None.
    """

    def load(
        self,
        path: str | Path,
        export_date: Optional[date] = None,
        source: ScreenerSource = ScreenerSource.TICKERTAPE,
        period_type: PeriodType = PeriodType.TTM,
    ) -> tuple[list[ScreenerRow], list[FundamentalSnapshot]]:
        """Parse CSV and return (screener_rows, fundamental_snapshots).

        Args:
            path:        Absolute path to the Tickertape CSV file.
            export_date: The date of this export (defaults to file mtime date).
            source:      ScreenerSource tag applied to every row.
            period_type: PeriodType for fundamental snapshots (default TTM).

        Returns:
            Tuple of (list[ScreenerRow], list[FundamentalSnapshot]).
            Both lists are parallel — one entry per valid symbol in the CSV.
        """
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("pandas is required for TickertapeLoader") from exc

        csv_path = Path(path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        exp_date = export_date or _mtime_date(csv_path)
        logger.info("Loading Tickertape CSV: %s (export_date=%s)", csv_path.name, exp_date)

        df = pd.read_csv(csv_path, dtype=str, na_filter=False)
        df.columns = [str(c).strip() for c in df.columns]
        alias_map = _build_alias_lookup(list(df.columns))

        logger.debug("Columns detected: %s", list(df.columns))
        logger.debug("Alias map resolved: %s", alias_map)

        screener_rows: list[ScreenerRow] = []
        fundamental_snaps: list[FundamentalSnapshot] = []
        skipped = 0

        for _, row in df.iterrows():
            raw_symbol = _get(row, alias_map, "symbol")
            if not raw_symbol:
                skipped += 1
                continue

            symbol = _clean_symbol(str(raw_symbol))
            if not symbol:
                skipped += 1
                continue

            row_id = str(uuid.uuid4())
            raw_row = {str(k): str(v) for k, v in row.items()}

            screener_rows.append(ScreenerRow(
                id=row_id,
                source=source,
                symbol=symbol,
                export_date=exp_date,
                company_name=_get(row, alias_map, "company_name"),
                sector=_get(row, alias_map, "sector"),
                market_cap_cr=_f(_get(row, alias_map, "market_cap_cr")),
                pe_ratio=_f(_get(row, alias_map, "pe_ratio")),
                pb_ratio=_f(_get(row, alias_map, "pb_ratio")),
                roce_pct=_f(_get(row, alias_map, "roce_pct")),
                roe_pct=_f(_get(row, alias_map, "roe_pct")),
                debt_to_equity=_f(_get(row, alias_map, "debt_to_equity")),
                revenue_growth_1y=_f(_get(row, alias_map, "revenue_growth_1y")),
                profit_growth_1y=_f(_get(row, alias_map, "profit_growth_1y")),
                dividend_yield_pct=_f(_get(row, alias_map, "dividend_yield_pct")),
                score_raw=_f(_get(row, alias_map, "score_raw")),
                raw_row=raw_row,
            ))

            fundamental_snaps.append(FundamentalSnapshot(
                id=str(uuid.uuid4()),
                symbol=symbol,
                period_end=exp_date,
                period_type=period_type,
                source=FundamentalSource.TICKERTAPE,
                pe_ratio=_f(_get(row, alias_map, "pe_ratio")),
                pb_ratio=_f(_get(row, alias_map, "pb_ratio")),
                roce_pct=_f(_get(row, alias_map, "roce_pct")),
                roe_pct=_f(_get(row, alias_map, "roe_pct")),
                debt_to_equity=_f(_get(row, alias_map, "debt_to_equity")),
                revenue_growth_1y=_f(_get(row, alias_map, "revenue_growth_1y")),
                profit_growth_1y=_f(_get(row, alias_map, "profit_growth_1y")),
                dividend_yield_pct=_f(_get(row, alias_map, "dividend_yield_pct")),
                eps=_f(_get(row, alias_map, "eps")),
                book_value_per_share=_f(_get(row, alias_map, "book_value_per_share")),
                raw_data=raw_row,
            ))

        logger.info(
            "Parsed %d rows (%d skipped) from %s",
            len(screener_rows), skipped, csv_path.name,
        )
        return screener_rows, fundamental_snaps

    def load_as_dataframe(self, path: str | Path):
        """Return the raw CSV as a normalised pandas DataFrame.

        Column names are renamed to canonical snake_case field names.
        Useful for ad-hoc analysis without going through the full model layer.
        """
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("pandas is required") from exc

        csv_path = Path(path)
        df = pd.read_csv(csv_path, dtype=str, na_filter=False)
        df.columns = [str(c).strip() for c in df.columns]
        alias_map = _build_alias_lookup(list(df.columns))

        rename = {v: k for k, v in alias_map.items()}
        return df.rename(columns=rename)


def _mtime_date(path: Path) -> date:
    """Return the file modification date as a fallback export_date."""
    return datetime.fromtimestamp(path.stat().st_mtime).date()
