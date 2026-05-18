"""Fundamental scorer: quality and valuation signals for a single instrument.

Pulls the latest FundamentalSnapshot from the `fundamentals` table and
scores across five dimensions.  Returns a composite score (0-10) with a
signal and structured reasoning.

Scoring rubric:

  ROCE — Return on Capital Employed (max 2.5 pts)
    > 25%  +2.5  |  15-25%  +1.5  |  10-15%  +0.5  |  < 10%  +0

  ROE — Return on Equity (max 2 pts)
    > 20%  +2  |  12-20%  +1  |  < 12%  +0

  Debt-to-Equity (max 2 pts)
    < 0.3  +2  |  0.3-1.0  +1  |  > 1.0  +0  |  > 2.0  flag!

  Valuation — PE ratio (max 2 pts)
    ETFs / index instruments skip PE (score neutral 1 pt).
    < 15   +2  |  15-25  +1  |  > 25  +0.5  |  > 40  +0

  Profit growth 1-year (max 1.5 pts)
    > 20%  +1.5  |  10-20%  +1  |  0-10%  +0.5  |  negative  +0

Signal thresholds (same as technical scorer for consistency):
  ≥ 7.5  →  STRONG
  5.0-7.5 →  GOOD
  3.0-5.0 →  FAIR
  < 3.0  →  WEAK
  NO_DATA →  no snapshot in DB
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.models.fundamental import FundamentalSnapshot, PeriodType
from investment_os.data_layer.repositories.fundamentals_repository import FundamentalsRepository

logger = get_logger(__name__)

# Instruments where PE/PB are meaningless (index ETFs, gold)
_ETF_KEYWORDS = frozenset([
    "BEES", "ETF", "NIFTY", "JUNIOR", "MOM100", "ICICIB22",
    "LIQUID", "CPSE", "PHARMA", "BANK", "METAL", "ENERGY",
    "DEFENCE", "MODEFENCE", "PSU", "INFRA",
])


def _is_etf(symbol: str) -> bool:
    s = symbol.upper()
    return any(k in s for k in _ETF_KEYWORDS)


@dataclass
class FundamentalScore:
    symbol: str
    score: float                          # 0-10
    signal: str                           # "STRONG" | "GOOD" | "FAIR" | "WEAK" | "NO_DATA"
    period_type: Optional[str] = None
    period_end: Optional[str] = None
    source: Optional[str] = None
    reasons: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)

    # Raw values surfaced for Claude reasoning
    roce_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    profit_growth_1y: Optional[float] = None
    revenue_growth_1y: Optional[float] = None
    promoter_holding_pct: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 2),
            "signal": self.signal,
            "period": {"type": self.period_type, "end": self.period_end, "source": self.source},
            "reasons": self.reasons,
            "flags": self.flags,
            "metrics": {
                "roce_pct": self.roce_pct,
                "roe_pct": self.roe_pct,
                "debt_to_equity": self.debt_to_equity,
                "pe_ratio": self.pe_ratio,
                "pb_ratio": self.pb_ratio,
                "profit_growth_1y_pct": self.profit_growth_1y,
                "revenue_growth_1y_pct": self.revenue_growth_1y,
                "promoter_holding_pct": self.promoter_holding_pct,
            },
        }


class FundamentalScorer:
    """Compute fundamental quality + valuation score from the DB."""

    def __init__(self, repo: Optional[FundamentalsRepository] = None) -> None:
        self._repo = repo or FundamentalsRepository()

    def score(
        self,
        symbol: str,
        period_type: PeriodType = PeriodType.TTM,
    ) -> FundamentalScore:
        """Return FundamentalScore for `symbol`.

        Looks up the most recent snapshot for the given period_type.
        Falls back to any available period_type if TTM is missing.
        Returns NO_DATA signal when no fundamental data exists.
        """
        snap = self._repo.get_latest(symbol, period_type)
        if snap is None and period_type != PeriodType.ANNUAL:
            snap = self._repo.get_latest(symbol, PeriodType.ANNUAL)

        if snap is None:
            return FundamentalScore(
                symbol=symbol, score=0.0, signal="NO_DATA",
                reasons=["No fundamental data in DB — import a Tickertape CSV first"],
            )
        return self._compute(symbol, snap)

    def score_from_snapshot(self, snap: FundamentalSnapshot) -> FundamentalScore:
        """Score from a pre-fetched snapshot (avoids extra DB query)."""
        return self._compute(snap.symbol, snap)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _compute(self, symbol: str, snap: FundamentalSnapshot) -> FundamentalScore:
        is_etf = _is_etf(symbol)
        total_score = 0.0
        reasons: list[str] = []
        flags: dict[str, bool] = {}

        result = FundamentalScore(
            symbol=symbol, score=0.0, signal="",
            period_type=snap.period_type if isinstance(snap.period_type, str) else snap.period_type.value,
            period_end=str(snap.period_end),
            source=snap.source if isinstance(snap.source, str) else snap.source.value,
            roce_pct=snap.roce_pct,
            roe_pct=snap.roe_pct,
            debt_to_equity=snap.debt_to_equity,
            pe_ratio=snap.pe_ratio,
            pb_ratio=snap.pb_ratio,
            profit_growth_1y=snap.profit_growth_1y,
            revenue_growth_1y=snap.revenue_growth_1y,
            promoter_holding_pct=snap.promoter_holding_pct,
        )

        # ── ROCE (max 2.5 pts) ────────────────────────────────────────────────
        if snap.roce_pct is not None:
            r = snap.roce_pct
            if r > 25:
                total_score += 2.5
                reasons.append(f"Excellent ROCE {r:.1f}% — capital highly productive")
                flags["high_roce"] = True
            elif r > 15:
                total_score += 1.5
                reasons.append(f"Good ROCE {r:.1f}%")
            elif r > 10:
                total_score += 0.5
                reasons.append(f"Moderate ROCE {r:.1f}% — below ideal threshold")
            else:
                reasons.append(f"Weak ROCE {r:.1f}% — poor capital deployment")
                flags["weak_roce"] = True
        elif not is_etf:
            reasons.append("ROCE data unavailable")

        # ── ROE (max 2 pts) ───────────────────────────────────────────────────
        if snap.roe_pct is not None:
            r = snap.roe_pct
            if r > 20:
                total_score += 2.0
                reasons.append(f"Strong ROE {r:.1f}%")
                flags["high_roe"] = True
            elif r > 12:
                total_score += 1.0
                reasons.append(f"Acceptable ROE {r:.1f}%")
            else:
                reasons.append(f"Low ROE {r:.1f}%")
        elif not is_etf:
            reasons.append("ROE data unavailable")

        # ── Debt-to-Equity (max 2 pts) ────────────────────────────────────────
        if snap.debt_to_equity is not None:
            de = snap.debt_to_equity
            if de < 0.3:
                total_score += 2.0
                reasons.append(f"Very low debt D/E {de:.2f} — balance sheet strength")
                flags["low_debt"] = True
            elif de <= 1.0:
                total_score += 1.0
                reasons.append(f"Manageable debt D/E {de:.2f}")
            else:
                reasons.append(f"Elevated debt D/E {de:.2f}")
                if de > 2.0:
                    flags["high_debt"] = True
                    reasons.append("⚠ D/E > 2 — leverage risk")
        elif not is_etf:
            reasons.append("Debt/equity data unavailable")

        # ── PE Valuation (max 2 pts) ──────────────────────────────────────────
        if is_etf:
            # PE is not meaningful for ETFs — award a neutral 1pt so ETFs
            # aren't penalised for missing data
            total_score += 1.0
            reasons.append("ETF/Index — PE valuation not applicable (neutral score)")
        elif snap.pe_ratio is not None:
            pe = snap.pe_ratio
            if pe <= 0:
                reasons.append(f"Negative PE ({pe:.1f}) — loss-making")
                flags["loss_making"] = True
            elif pe < 15:
                total_score += 2.0
                reasons.append(f"Attractive PE {pe:.1f}x — undervalued")
                flags["value"] = True
            elif pe <= 25:
                total_score += 1.0
                reasons.append(f"Fair PE {pe:.1f}x")
            elif pe <= 40:
                total_score += 0.5
                reasons.append(f"Elevated PE {pe:.1f}x — priced for growth")
            else:
                reasons.append(f"Very high PE {pe:.1f}x — expensive")
                flags["expensive"] = True
        else:
            reasons.append("PE data unavailable")

        # ── Profit growth 1y (max 1.5 pts) ───────────────────────────────────
        if snap.profit_growth_1y is not None:
            g = snap.profit_growth_1y
            if g > 20:
                total_score += 1.5
                reasons.append(f"Strong profit growth {g:+.1f}% YoY")
                flags["profit_growth"] = True
            elif g > 10:
                total_score += 1.0
                reasons.append(f"Decent profit growth {g:+.1f}% YoY")
            elif g > 0:
                total_score += 0.5
                reasons.append(f"Slow profit growth {g:+.1f}% YoY")
            else:
                reasons.append(f"Profit declined {g:+.1f}% YoY")
                flags["profit_decline"] = True
        elif not is_etf:
            reasons.append("Profit growth data unavailable")

        # ── Promoter holding (informational flag only) ────────────────────────
        if snap.promoter_holding_pct is not None:
            ph = snap.promoter_holding_pct
            if ph < 40:
                flags["low_promoter_holding"] = True
                reasons.append(f"⚠ Low promoter holding {ph:.1f}% — monitor for selling")
            elif ph > 65:
                flags["high_promoter_holding"] = True
                reasons.append(f"High promoter holding {ph:.1f}% — aligned interests")

        # ── Signal ────────────────────────────────────────────────────────────
        total_score = min(total_score, 10.0)
        if total_score >= 7.5:
            signal = "STRONG"
        elif total_score >= 5.0:
            signal = "GOOD"
        elif total_score >= 3.0:
            signal = "FAIR"
        else:
            signal = "WEAK"

        result.score = round(total_score, 2)
        result.signal = signal
        result.reasons = reasons
        result.flags = flags

        logger.debug("FundamentalScore %s: %.1f (%s)", symbol, total_score, signal)
        return result
