"""Read-only loader for the Investment OS JSON state files.

All state files live in the project root (one level above investment-os/).
This loader NEVER writes to them — they are the authoritative source of
truth for the Claude skill system (SKILL-02, SKILL-04, etc.).

The loader returns typed Pydantic models so downstream code has a
consistent interface regardless of JSON structure changes.

Usage:
    from investment_os.data_layer.loaders.json_state_loader import JsonStateLoader

    loader = JsonStateLoader()
    watchlist  = loader.load_watchlist()
    allocation = loader.load_target_allocation()
    state      = loader.load_portfolio_state()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from investment_os.core.logging import get_logger

logger = get_logger(__name__)

# Root of the Investing/ project (two levels above the backend/ directory)
_INVESTING_ROOT = Path(__file__).resolve().parents[6]


def _investing_root() -> Path:
    """Resolve the Investing/ root at call time (easier to patch in tests)."""
    return _INVESTING_ROOT


def _read_json(filename: str) -> dict[str, Any]:
    path = _investing_root() / filename
    if not path.exists():
        logger.warning("State file not found: %s", path)
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        logger.debug("Loaded %s (%d bytes)", filename, len(text))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.error("Failed to parse %s: %s", filename, exc)
        return {}


# ── Typed result models ────────────────────────────────────────────────────────

@dataclass
class WatchlistInstrument:
    symbol: str              # bare NSE symbol, e.g. "NIFTYBEES"
    kite_token: int
    bucket: str
    sector: Optional[str] = None
    priority: int = 2
    current_score: Optional[float] = None
    decision: Optional[str] = None

    @property
    def nse_full(self) -> str:
        """Returns "NSE:SYMBOL" format."""
        return f"NSE:{self.symbol}"


@dataclass
class WatchlistConfig:
    core: list[WatchlistInstrument] = field(default_factory=list)
    sector_rotation: list[WatchlistInstrument] = field(default_factory=list)
    active_sector_etf: Optional[str] = None   # bare symbol, e.g. "CPSEETF"
    last_updated: Optional[str] = None

    @property
    def all_instruments(self) -> list[WatchlistInstrument]:
        """All instruments (core + sector), deduplicated by symbol."""
        seen: set[str] = set()
        result: list[WatchlistInstrument] = []
        for inst in self.core + self.sector_rotation:
            if inst.symbol not in seen:
                seen.add(inst.symbol)
                result.append(inst)
        return result

    @property
    def symbol_to_token(self) -> dict[str, int]:
        """Return {bare_symbol: kite_token} for all instruments."""
        return {inst.symbol: inst.kite_token for inst in self.all_instruments}


@dataclass
class ApprovedInstrument:
    symbol: str              # bare NSE symbol
    kite_token: int
    name: str
    bucket: str
    expense_ratio_pct: Optional[float] = None
    tracks: Optional[str] = None
    approved: bool = True


@dataclass
class AllocationBucket:
    bucket: str
    target_pct: float
    monthly_inr: float
    instruments: list[str] = field(default_factory=list)   # bare symbols
    rationale: Optional[str] = None


@dataclass
class AllocationConfig:
    monthly_budget_inr: float
    rebalance_tolerance_pct: float
    buckets: list[AllocationBucket] = field(default_factory=list)
    last_updated: Optional[str] = None

    @property
    def bucket_map(self) -> dict[str, AllocationBucket]:
        return {b.bucket: b for b in self.buckets}


@dataclass
class TrailingStop:
    symbol: str
    stop_price: float
    peak_price: float
    buffer_pct: float
    status: str = "ACTIVE"


@dataclass
class PortfolioState:
    """Lightweight read-only view of portfolio_state.json.

    Only extracts the fields that the ingestion pipeline and analysis tools
    actually need.  Heavy fields (full execution log, orders) are omitted.
    """
    month: Optional[str] = None
    total_budget_inr: float = 400_000
    deployed_inr: float = 0.0
    remaining_inr: float = 0.0
    trading_days_remaining: int = 0
    available_cash_inr: float = 0.0
    trailing_stops: list[TrailingStop] = field(default_factory=list)
    last_updated: Optional[str] = None


# ── Loader ────────────────────────────────────────────────────────────────────

class JsonStateLoader:
    """Read-only access to the Investing/ JSON state files.

    All methods return typed dataclasses.  Missing or malformed files return
    safe empty defaults — callers don't need to handle None.
    """

    # ── watchlist.json ────────────────────────────────────────────────────────

    def load_watchlist(self) -> WatchlistConfig:
        """Parse watchlist.json → WatchlistConfig."""
        data = _read_json("watchlist.json")
        if not data:
            return WatchlistConfig()

        def _parse_inst(d: dict, bucket_fallback: str = "") -> WatchlistInstrument:
            raw_sym = d.get("symbol", "")
            symbol = raw_sym.replace("NSE:", "").replace("BSE:", "").strip().upper()
            return WatchlistInstrument(
                symbol=symbol,
                kite_token=int(d.get("token", 0)),
                bucket=d.get("bucket", bucket_fallback),
                sector=d.get("sector"),
                priority=int(d.get("priority", 2)),
                current_score=_safe_float(d.get("current_score")),
                decision=d.get("decision"),
            )

        core = [_parse_inst(d) for d in data.get("core_always_watch", [])]
        sector = [_parse_inst(d) for d in data.get("sector_rotation_watch", [])]

        raw_active = data.get("active_sector_etf", "")
        active = raw_active.replace("NSE:", "").replace("BSE:", "").strip().upper() if raw_active else None

        return WatchlistConfig(
            core=core,
            sector_rotation=sector,
            active_sector_etf=active,
            last_updated=data.get("last_updated"),
        )

    # ── approved_instruments.json ─────────────────────────────────────────────

    def load_approved_instruments(self) -> list[ApprovedInstrument]:
        """Parse approved_instruments.json → list[ApprovedInstrument]."""
        data = _read_json("approved_instruments.json")
        result: list[ApprovedInstrument] = []
        for d in data.get("instruments", []):
            raw_sym = d.get("symbol", "")
            symbol = raw_sym.replace("NSE:", "").replace("BSE:", "").strip().upper()
            if not symbol:
                continue
            result.append(ApprovedInstrument(
                symbol=symbol,
                kite_token=int(d.get("token", 0)),
                name=d.get("name", symbol),
                bucket=d.get("bucket", ""),
                expense_ratio_pct=_safe_float(d.get("expense_ratio_pct")),
                tracks=d.get("tracks"),
                approved=bool(d.get("approved", True)),
            ))
        logger.debug("Loaded %d approved instruments", len(result))
        return result

    def load_approved_symbol_to_token(self) -> dict[str, int]:
        """Return {bare_symbol: kite_token} for all approved instruments."""
        return {i.symbol: i.kite_token for i in self.load_approved_instruments() if i.kite_token}

    # ── target_allocation.json ────────────────────────────────────────────────

    def load_target_allocation(self) -> AllocationConfig:
        """Parse target_allocation.json → AllocationConfig."""
        data = _read_json("target_allocation.json")
        if not data:
            return AllocationConfig(monthly_budget_inr=400_000, rebalance_tolerance_pct=5)

        buckets = []
        for b in data.get("allocation", []):
            instruments = [
                s.replace("NSE:", "").replace("BSE:", "").strip().upper()
                for s in b.get("instruments", [])
            ]
            buckets.append(AllocationBucket(
                bucket=b.get("bucket", ""),
                target_pct=float(b.get("target_pct", 0)),
                monthly_inr=float(b.get("monthly_inr", 0)),
                instruments=instruments,
                rationale=b.get("rationale"),
            ))

        return AllocationConfig(
            monthly_budget_inr=float(data.get("monthly_budget_inr", 400_000)),
            rebalance_tolerance_pct=float(data.get("rebalance_tolerance_pct", 5)),
            buckets=buckets,
            last_updated=data.get("last_updated"),
        )

    # ── portfolio_state.json ──────────────────────────────────────────────────

    def load_portfolio_state(self) -> PortfolioState:
        """Parse portfolio_state.json → PortfolioState (lightweight subset).

        Only pulls fields used by ingestion and analysis — does not attempt
        to parse the full execution history.
        """
        data = _read_json("portfolio_state.json")
        if not data:
            return PortfolioState()

        budget = data.get("monthly_budget", {})
        kite = data.get("kite_account", {})

        # Parse trailing stops — supports both list and {positions: [...]} shapes
        stops: list[TrailingStop] = []
        ts_raw = data.get("trailing_stops", [])
        if isinstance(ts_raw, dict):
            ts_raw = ts_raw.get("positions", [])
        for raw in ts_raw:
            if not isinstance(raw, dict):
                continue
            sym = raw.get("symbol", "").upper().strip()
            if not sym:
                continue
            stops.append(TrailingStop(
                symbol=sym,
                stop_price=float(raw.get("stop", raw.get("stop_price", 0))),
                peak_price=float(raw.get("peak", raw.get("peak_price", 0))),
                buffer_pct=float(raw.get("buffer_pct") or 8),
                status=raw.get("status", "ACTIVE"),
            ))

        return PortfolioState(
            month=budget.get("month"),
            total_budget_inr=float(budget.get("total_inr", 400_000)),
            deployed_inr=float(budget.get("deployed_inr", 0)),
            remaining_inr=float(budget.get("remaining_inr", 0)),
            trading_days_remaining=int(budget.get("trading_days_remaining", 0)),
            available_cash_inr=float(kite.get("available_cash_inr", 0)),
            trailing_stops=stops,
            last_updated=data.get("last_updated"),
        )

    # ── Convenience: all watchlist symbols with tokens ─────────────────────────

    def get_ingest_targets(self) -> list[WatchlistInstrument]:
        """Return all instruments that should be fetched in daily price ingestion.

        Merges watchlist + approved instruments (token data from watchlist wins).
        Only includes instruments with a valid Kite token.
        """
        watchlist = self.load_watchlist()
        token_map = watchlist.symbol_to_token

        # Fill in any approved instruments missing from watchlist
        for inst in self.load_approved_instruments():
            if inst.symbol not in token_map and inst.kite_token:
                token_map[inst.symbol] = inst.kite_token

        # Build final list from watchlist (which has richer metadata)
        result = [i for i in watchlist.all_instruments if i.kite_token]

        # Add approved-only instruments not already in result
        seen = {i.symbol for i in result}
        for inst in self.load_approved_instruments():
            if inst.symbol not in seen and inst.kite_token:
                result.append(WatchlistInstrument(
                    symbol=inst.symbol,
                    kite_token=inst.kite_token,
                    bucket=inst.bucket,
                ))

        logger.info("Ingest targets: %d instruments", len(result))
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(v) -> Optional[float]:
    if v is None or str(v).strip() in ("", "null", "N/A"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
