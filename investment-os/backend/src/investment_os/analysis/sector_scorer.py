"""Sector scorer: reads sector_rotation.json + live price data.

Provides two views:

  1. Archived view (sector_rotation.json)
     Directly returns SKILL-04's computed scores, decisions, and notes —
     the authoritative source for rotation decisions.

  2. Live price refresh (optional)
     Re-computes technical scores for each ETF from stored OHLCV bars
     and annotates the archived data with fresh momentum / RSI figures.
     Does NOT override SKILL-04's fundamental / FII-DII scores.

Usage:
    from investment_os.analysis.sector_scorer import SectorScorer

    scorer = SectorScorer()
    data = scorer.get_current_data()          # archived + optional live refresh
    ranked = scorer.get_ranked_sectors()      # list sorted by composite_score DESC
    active = scorer.get_active_sector_etf()   # "CPSEETF"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.repositories.price_repository import PriceRepository

logger = get_logger(__name__)

_INVESTING_ROOT = Path(__file__).resolve().parents[5]


def _read_sector_rotation() -> dict[str, Any]:
    path = _INVESTING_ROOT / "sector_rotation.json"
    if not path.exists():
        logger.warning("sector_rotation.json not found at %s", path)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to parse sector_rotation.json: %s", exc)
        return {}


@dataclass
class SectorEntry:
    rank: int
    sector: str
    etf: str                        # bare symbol, e.g. "CPSEETF"
    etf_full: str                   # "NSE:CPSEETF"
    kite_token: int
    composite_score: float
    technical_score: Optional[float]
    fundamental_score: Optional[float]
    fii_dii_score: Optional[float]
    decision: str                   # "BUY" | "HOLD" | "WATCH" | "AVOID" | "STOPPED"
    monthly_allocation_inr: float
    current_price: Optional[float]
    notes: Optional[str]
    rsi14: Optional[float] = None
    dma_detail: Optional[str] = None
    # Live-refresh fields (populated by get_current_data(refresh=True))
    live_rsi: Optional[float] = None
    live_momentum_20d: Optional[float] = None
    live_close: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "rank": self.rank,
            "sector": self.sector,
            "etf": self.etf,
            "kite_token": self.kite_token,
            "scores": {
                "composite": self.composite_score,
                "technical": self.technical_score,
                "fundamental": self.fundamental_score,
                "fii_dii": self.fii_dii_score,
            },
            "decision": self.decision,
            "monthly_allocation_inr": self.monthly_allocation_inr,
            "current_price": self.current_price,
            "rsi14": self.rsi14,
            "dma_detail": self.dma_detail,
            "notes": self.notes,
            "live": {
                "rsi": self.live_rsi,
                "momentum_20d_pct": self.live_momentum_20d,
                "close": self.live_close,
            } if any([self.live_rsi, self.live_momentum_20d, self.live_close]) else None,
        }


@dataclass
class SectorRotationData:
    month: str
    generated_date: str
    active_sector_etf: str          # bare symbol
    active_sector_score: float
    rotation_decision: str
    sectors: list[SectorEntry] = field(default_factory=list)
    history_months: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "month": self.month,
            "generated_date": self.generated_date,
            "active_sector_etf": self.active_sector_etf,
            "active_sector_score": self.active_sector_score,
            "rotation_decision": self.rotation_decision,
            "sectors": [s.as_dict() for s in self.sectors],
            "history_months_available": self.history_months,
        }


class SectorScorer:
    """Read + annotate sector rotation data for Claude analysis."""

    def __init__(self, price_repo: Optional[PriceRepository] = None) -> None:
        self._price_repo = price_repo or PriceRepository()

    def get_current_data(self, refresh_live: bool = False) -> SectorRotationData:
        """Return current-month sector data.

        Args:
            refresh_live: If True, fetch stored OHLCV bars and overlay
                         live RSI / momentum on each sector entry.
                         Requires price ingestion to have run recently.

        Returns:
            SectorRotationData with all sectors ranked.
        """
        raw = _read_sector_rotation()
        if not raw:
            return SectorRotationData(
                month="unknown", generated_date="unknown",
                active_sector_etf="", active_sector_score=0.0,
                rotation_decision="sector_rotation.json not found",
            )

        current = raw.get("current_month", {})
        # history is a list of monthly dicts, not a keyed dict
        history_raw = raw.get("history", [])
        if isinstance(history_raw, list):
            history_keys = [h.get("month", "") for h in history_raw if isinstance(h, dict)]
        else:
            history_keys = list(history_raw.keys())

        active_raw = current.get("active_sector_etf", "")
        active_etf = active_raw.replace("NSE:", "").replace("BSE:", "").strip().upper()

        entries: list[SectorEntry] = []
        for s in current.get("scores", []):
            raw_etf = s.get("etf", "")
            etf = raw_etf.replace("NSE:", "").replace("BSE:", "").strip().upper()
            tech_detail = s.get("technical_detail", {})

            entry = SectorEntry(
                rank=int(s.get("rank", 99)),
                sector=s.get("sector", ""),
                etf=etf,
                etf_full=raw_etf if raw_etf.startswith("NSE:") else f"NSE:{etf}",
                kite_token=int(s.get("token", 0)),
                composite_score=float(s.get("composite_score", 0)),
                technical_score=_f(s.get("technical_score")),
                fundamental_score=_f(s.get("fundamental_score")),
                fii_dii_score=_f(s.get("fii_dii_score")),
                decision=s.get("decision", "WATCH"),
                monthly_allocation_inr=float(s.get("monthly_allocation_inr", 0)),
                current_price=_f(s.get("current_price")),
                notes=s.get("notes"),
                rsi14=_f(tech_detail.get("rsi14")),
                dma_detail=tech_detail.get("price_vs_200dma") or tech_detail.get("price_vs_50dma"),
            )
            entries.append(entry)

        entries.sort(key=lambda e: e.composite_score, reverse=True)

        data = SectorRotationData(
            month=current.get("month", ""),
            generated_date=current.get("generated_date", ""),
            active_sector_etf=active_etf,
            active_sector_score=float(current.get("active_sector_score", 0)),
            rotation_decision=current.get("rotation_decision", ""),
            sectors=entries,
            history_months=history_keys,
        )

        if refresh_live:
            self._overlay_live(data)

        return data

    def get_ranked_sectors(self, refresh_live: bool = False) -> list[SectorEntry]:
        """Return sectors sorted by composite_score descending."""
        return self.get_current_data(refresh_live=refresh_live).sectors

    def get_active_sector_etf(self) -> str:
        """Return the active sector ETF bare symbol (e.g. "CPSEETF")."""
        return self.get_current_data().active_sector_etf

    def get_buy_candidates(self) -> list[SectorEntry]:
        """Return sectors with decision == BUY, ranked by score."""
        return [s for s in self.get_ranked_sectors() if s.decision == "BUY"]

    def get_sector_history(self, etf: str) -> list[dict[str, Any]]:
        """Return historical monthly scores for a specific ETF symbol.

        Iterates the `history` key in sector_rotation.json.
        """
        raw = _read_sector_rotation()
        etf = etf.upper().replace("NSE:", "")
        result: list[dict] = []

        history_raw = raw.get("history", [])
        # history may be a list of month-dicts or a keyed dict
        if isinstance(history_raw, dict):
            history_items = history_raw.values()
        else:
            history_items = history_raw  # list of dicts

        for month_data in history_items:
            if not isinstance(month_data, dict):
                continue
            month_key = month_data.get("month", "")
            for s in month_data.get("scores", []):
                raw_etf = s.get("etf", "").replace("NSE:", "").upper()
                if raw_etf == etf:
                    result.append({
                        "month": month_key,
                        "composite_score": s.get("composite_score"),
                        "decision": s.get("decision"),
                        "current_price": s.get("current_price"),
                    })
                    break

        result.sort(key=lambda x: x["month"])
        return result

    # ── Live overlay ──────────────────────────────────────────────────────────

    def _overlay_live(self, data: SectorRotationData) -> None:
        """Overlay live RSI and momentum from price DB onto each sector entry."""
        from datetime import date, timedelta
        from investment_os.analysis.technical_scorer import TechnicalScorer

        scorer = TechnicalScorer(repo=self._price_repo)
        for entry in data.sectors:
            try:
                ts = scorer.score(entry.etf)
                if ts.signal != "NO_DATA":
                    entry.live_rsi = ts.rsi14
                    entry.live_momentum_20d = ts.momentum_20d_pct
                    entry.live_close = ts.current_price
                    logger.debug("Live overlay %s: RSI %.1f  mom20d %.1f%%",
                                 entry.etf, ts.rsi14 or 0, ts.momentum_20d_pct or 0)
            except Exception as exc:
                logger.warning("Live overlay failed for %s: %s", entry.etf, exc)


def _f(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
