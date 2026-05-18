"""Daily OHLCV price ingestion pipeline.

Fetches price bars for all watchlist instruments and writes them to the
`historical_prices` DuckDB table via PriceRepository.

Strategy:
  - For each instrument, check the latest date already in DB.
  - Only fetch bars from (latest_date + 1 day) onwards — never re-fetches.
  - Primary source: Kite historical_data API (requires valid access token).
  - Automatic fallback: yfinance (appends .NS) when Kite fails for any symbol.
  - If both fail, the symbol is logged as skipped — pipeline continues.

Usage:
    from investment_os.data_layer.ingestion.price_ingestion import PriceIngestion

    result = PriceIngestion().run()
    # or for a single symbol (useful in tests / manual runs):
    result = PriceIngestion().run_symbol("NIFTYBEES", token=2707457)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.clients.kite_client import KiteAuthError, KiteClient
from investment_os.data_layer.clients.yfinance_client import YfinanceClient, nse_ticker
from investment_os.data_layer.loaders.json_state_loader import JsonStateLoader, WatchlistInstrument
from investment_os.data_layer.models.price import OHLCBar, PriceHistory
from investment_os.data_layer.repositories.price_repository import PriceRepository

logger = get_logger(__name__)

# Rolling window: fetch at most this many calendar days at once
_DEFAULT_LOOKBACK_DAYS = 60
# Minimum gap before re-fetching (avoid hammering Kite for same-day runs)
_MIN_FETCH_GAP_DAYS = 1


@dataclass
class SymbolResult:
    symbol: str
    source: str          # "kite" | "yfinance" | "skipped"
    bars_fetched: int = 0
    bars_inserted: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.source != "skipped"


@dataclass
class IngestionResult:
    started_at: date = field(default_factory=date.today)
    symbols: list[SymbolResult] = field(default_factory=list)

    @property
    def total_bars(self) -> int:
        return sum(r.bars_fetched for r in self.symbols)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.symbols if r.ok)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.symbols if r.source == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.symbols if r.error is not None)

    def summary(self) -> str:
        return (
            f"Price ingestion: {self.success_count} ok, "
            f"{self.skipped_count} skipped, {self.failed_count} failed, "
            f"{self.total_bars} bars total"
        )


class PriceIngestion:
    """Orchestrates daily OHLCV fetch → PriceRepository write for all watchlist instruments."""

    def __init__(
        self,
        kite_client: Optional[KiteClient] = None,
        yf_client: Optional[YfinanceClient] = None,
        repo: Optional[PriceRepository] = None,
        loader: Optional[JsonStateLoader] = None,
        lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        self._kite = kite_client or KiteClient()
        self._yf = yf_client or YfinanceClient()
        self._repo = repo or PriceRepository()
        self._loader = loader or JsonStateLoader()
        self._lookback_days = lookback_days

    # ── Main entry points ─────────────────────────────────────────────────────

    def run(self, instruments: Optional[list[WatchlistInstrument]] = None) -> IngestionResult:
        """Run ingestion for all watchlist instruments (or a supplied subset).

        Args:
            instruments: Override the watchlist. If None, loads from watchlist.json.

        Returns:
            IngestionResult with per-symbol details and summary stats.
        """
        targets = instruments or self._loader.get_ingest_targets()
        logger.info("Starting price ingestion for %d instruments", len(targets))

        result = IngestionResult()
        kite_available = self._check_kite()

        for inst in targets:
            sym_result = self._ingest_one(inst, kite_available=kite_available)
            result.symbols.append(sym_result)
            if sym_result.ok:
                logger.info(
                    "  ✓ %s via %s — %d bars",
                    inst.symbol, sym_result.source, sym_result.bars_fetched,
                )
            elif sym_result.source == "skipped":
                logger.info("  — %s skipped (already up to date)", inst.symbol)
            else:
                logger.warning("  ✗ %s failed: %s", inst.symbol, sym_result.error)

        logger.info(result.summary())
        return result

    def run_symbol(
        self,
        symbol: str,
        token: Optional[int] = None,
        days: int = _DEFAULT_LOOKBACK_DAYS,
    ) -> SymbolResult:
        """Fetch and store price bars for a single symbol.

        Useful for manual backfill or testing without the full watchlist.
        """
        inst = WatchlistInstrument(
            symbol=symbol.upper(),
            kite_token=token or self._lookup_token(symbol),
            bucket="",
        )
        return self._ingest_one(inst, kite_available=self._check_kite(), force_days=days)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _check_kite(self) -> bool:
        try:
            return self._kite.is_connected()
        except Exception:
            logger.warning("Kite connection check failed — will use yfinance fallback for all")
            return False

    def _ingest_one(
        self,
        inst: WatchlistInstrument,
        *,
        kite_available: bool,
        force_days: Optional[int] = None,
    ) -> SymbolResult:
        """Fetch + store bars for one instrument. Returns SymbolResult."""

        from_date, to_date = self._date_range(inst.symbol, force_days)

        if from_date > to_date:
            return SymbolResult(symbol=inst.symbol, source="skipped")

        # ── Try Kite first ────────────────────────────────────────────────────
        if kite_available and inst.kite_token:
            try:
                bars = self._fetch_kite(inst.kite_token, from_date, to_date)
                if bars:
                    _set_symbol(bars, inst.symbol)
                    inserted = self._repo.upsert_bars(bars)
                    return SymbolResult(
                        symbol=inst.symbol, source="kite",
                        bars_fetched=len(bars), bars_inserted=inserted,
                    )
            except KiteAuthError as exc:
                logger.warning("Kite auth error for %s — falling back: %s", inst.symbol, exc)
                kite_available = False  # stop trying Kite for this run
            except Exception as exc:
                logger.warning("Kite fetch failed for %s — falling back: %s", inst.symbol, exc)

        # ── yfinance fallback ─────────────────────────────────────────────────
        try:
            bars = self._fetch_yfinance(inst.symbol, from_date, to_date)
            if bars:
                _set_symbol(bars, inst.symbol)
                inserted = self._repo.upsert_bars(bars)
                return SymbolResult(
                    symbol=inst.symbol, source="yfinance",
                    bars_fetched=len(bars), bars_inserted=inserted,
                )
            # yfinance returned empty (e.g. weekend / holiday)
            return SymbolResult(symbol=inst.symbol, source="skipped")
        except Exception as exc:
            return SymbolResult(
                symbol=inst.symbol, source="skipped",
                error=f"Both Kite and yfinance failed: {exc}",
            )

    def _date_range(self, symbol: str, force_days: Optional[int]) -> tuple[date, date]:
        """Compute (from_date, to_date) for the fetch window.

        - to_date is always today.
        - from_date is (latest_in_db + 1 day), capped at `lookback_days` ago.
        - If force_days is set, ignore the DB and use a fixed window.
        """
        to_date = date.today()

        if force_days:
            return to_date - timedelta(days=force_days), to_date

        latest = self._repo.get_latest_date(symbol)
        if latest:
            from_date = latest + timedelta(days=_MIN_FETCH_GAP_DAYS)
        else:
            from_date = to_date - timedelta(days=self._lookback_days)

        return from_date, to_date

    def _fetch_kite(self, token: int, from_date: date, to_date: date) -> list[OHLCBar]:
        """Fetch from Kite. Raises on auth/API errors so caller can fallback."""
        from_str = from_date.strftime("%Y-%m-%d %H:%M:%S")
        to_str = to_date.strftime("%Y-%m-%d %H:%M:%S")
        return self._kite.get_historical_data(token, from_str, to_str, interval="day")

    def _fetch_yfinance(self, symbol: str, from_date: date, to_date: date) -> list[OHLCBar]:
        return self._yf.get_ohlcv(nse_ticker(symbol), start=from_date, end=to_date)

    def _lookup_token(self, symbol: str) -> int:
        """Look up a Kite token from watchlist/approved JSON files."""
        token_map = self._loader.load_watchlist().symbol_to_token
        return token_map.get(symbol.upper(), 0)


def _set_symbol(bars: list[OHLCBar], symbol: str) -> None:
    """Backfill symbol field on bars that don't have it set (Kite bars)."""
    for b in bars:
        if not b.symbol:
            object.__setattr__(b, "symbol", symbol)
