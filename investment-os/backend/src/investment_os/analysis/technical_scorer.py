"""Technical scorer: price-action signals for a single instrument.

Computes RSI-14, 20-DMA, 50-DMA, momentum (20d/60d), volume ratio, and
52-week range position from stored OHLCV bars, then combines them into a
composite technical score (0-10) with a signal label and human-readable
reasoning.

Scoring rubric (mirrors the SKILL-04 logic in sector_rotation.json):

  DMA position (max 3 pts)
    price > 200-DMA  +3  |  price > 50-DMA only  +2  |  below both  +0
    (50-DMA used as proxy when <200 bars; falls back gracefully)

  RSI-14 (max 2 pts)
    30-60 (oversold recovery)  +2
    60-70 (bullish momentum)   +1.5
    <30 (deep oversold)        +1   ← bounce candidate but risky
    >70 (overbought)           +0.5

  20-day momentum (max 2 pts)
    > +3%  +2  |  0 to +3%  +1  |  negative  +0

  Volume ratio 20d/60d (max 1 pt)
    > 1.2 (rising volume)  +1  |  0.8-1.2  +0.5  |  < 0.8  +0

  52-week range position (max 2 pts)
    > 80th pct  +2  |  50-80th  +1  |  < 50th  +0

Signal thresholds:
  ≥ 8.0  →  BUY
  6.0-8.0 →  HOLD
  4.0-6.0 →  WATCH
  < 4.0  →  AVOID
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from investment_os.core.logging import get_logger
from investment_os.data_layer.models.price import PriceHistory
from investment_os.data_layer.repositories.price_repository import PriceRepository

logger = get_logger(__name__)

_MIN_BARS_REQUIRED = 20   # can't score with fewer bars
_LOOKBACK_DAYS = 280      # ~1 trading year + buffer for 200-DMA


@dataclass
class TechnicalScore:
    symbol: str
    score: float                          # 0-10
    signal: str                           # "BUY" | "HOLD" | "WATCH" | "AVOID" | "NO_DATA"
    reasons: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)

    # Raw indicators (None = insufficient data)
    rsi14: Optional[float] = None
    dma_20: Optional[float] = None
    dma_50: Optional[float] = None
    dma_200: Optional[float] = None
    current_price: Optional[float] = None
    momentum_20d_pct: Optional[float] = None
    momentum_60d_pct: Optional[float] = None
    volume_ratio_20_60: Optional[float] = None
    week52_position_pct: Optional[float] = None
    bars_used: int = 0

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 2),
            "signal": self.signal,
            "reasons": self.reasons,
            "flags": self.flags,
            "indicators": {
                "current_price": self.current_price,
                "rsi14": _r(self.rsi14),
                "dma_20": _r(self.dma_20),
                "dma_50": _r(self.dma_50),
                "dma_200": _r(self.dma_200),
                "momentum_20d_pct": _r(self.momentum_20d_pct),
                "momentum_60d_pct": _r(self.momentum_60d_pct),
                "volume_ratio_20_60": _r(self.volume_ratio_20_60),
                "week52_position_pct": _r(self.week52_position_pct),
                "bars_used": self.bars_used,
            },
        }


class TechnicalScorer:
    """Compute technical score for any instrument in the price DB."""

    def __init__(self, repo: Optional[PriceRepository] = None) -> None:
        self._repo = repo or PriceRepository()

    def score(self, symbol: str) -> TechnicalScore:
        """Return TechnicalScore for `symbol`.

        Fetches up to 280 calendar days of bars from the DB (no network call).
        Returns a NO_DATA signal if fewer than 20 bars are available.
        """
        history = self._repo.get_bars(
            symbol,
            from_date=date.today() - timedelta(days=_LOOKBACK_DAYS),
        )

        if len(history) < _MIN_BARS_REQUIRED:
            logger.warning("TechnicalScorer: insufficient bars for %s (%d)", symbol, len(history))
            return TechnicalScore(
                symbol=symbol, score=0.0, signal="NO_DATA",
                reasons=[f"Only {len(history)} bars available — run price ingestion first"],
            )

        return self._compute(symbol, history)

    def score_from_history(self, history: PriceHistory) -> TechnicalScore:
        """Score from a pre-fetched PriceHistory (avoids extra DB query)."""
        if len(history) < _MIN_BARS_REQUIRED:
            return TechnicalScore(
                symbol=history.symbol, score=0.0, signal="NO_DATA",
                reasons=[f"Only {len(history)} bars available"],
            )
        return self._compute(history.symbol, history)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _compute(self, symbol: str, history: PriceHistory) -> TechnicalScore:
        closes = history.closes()
        volumes = [b.volume for b in history.bars]
        n = len(closes)
        price = closes[-1]

        result = TechnicalScore(
            symbol=symbol, score=0.0, signal="",
            current_price=round(price, 2),
            bars_used=n,
        )

        total_score = 0.0
        reasons: list[str] = []
        flags: dict[str, bool] = {}

        # ── RSI-14 (max 2 pts) ────────────────────────────────────────────────
        rsi = _rsi(closes)
        result.rsi14 = _r(rsi)
        if rsi is not None:
            if rsi < 30:
                total_score += 1.0
                reasons.append(f"RSI {rsi:.1f} — deeply oversold (bounce risk)")
                flags["oversold"] = True
            elif rsi <= 60:
                total_score += 2.0
                reasons.append(f"RSI {rsi:.1f} — healthy range (room to run)")
            elif rsi <= 70:
                total_score += 1.5
                reasons.append(f"RSI {rsi:.1f} — bullish momentum")
            else:
                total_score += 0.5
                reasons.append(f"RSI {rsi:.1f} — overbought (caution)")
                flags["overbought"] = True

        # ── DMA position (max 3 pts) ──────────────────────────────────────────
        dma20 = _dma(closes, 20)
        dma50 = _dma(closes, 50) if n >= 50 else None
        dma200 = _dma(closes, 200) if n >= 200 else None

        result.dma_20 = _r(dma20)
        result.dma_50 = _r(dma50)
        result.dma_200 = _r(dma200)

        reference_dma = dma200 or dma50  # use 200 when available, 50 as proxy

        if reference_dma is not None:
            pct_above = (price - reference_dma) / reference_dma * 100
            if price > reference_dma:
                if dma200:
                    total_score += 3.0
                    reasons.append(f"Above 200-DMA by {pct_above:+.1f}% — strong uptrend")
                    flags["above_200dma"] = True
                else:
                    total_score += 2.0
                    reasons.append(f"Above 50-DMA by {pct_above:+.1f}% (200-DMA unavailable)")
                    flags["above_50dma"] = True
            else:
                reasons.append(f"Below long-term DMA by {pct_above:.1f}% — weakness")
                flags["below_dma"] = True

        if dma50 and price > dma50 and not flags.get("above_200dma"):
            flags["above_50dma"] = True

        # ── 20-day momentum (max 2 pts) ───────────────────────────────────────
        mom20 = history.pct_change(days=min(20, n - 1))
        result.momentum_20d_pct = _r(mom20)
        if mom20 is not None:
            if mom20 > 3:
                total_score += 2.0
                reasons.append(f"Strong 20d momentum: {mom20:+.1f}%")
                flags["strong_momentum"] = True
            elif mom20 > 0:
                total_score += 1.0
                reasons.append(f"Positive 20d momentum: {mom20:+.1f}%")
            else:
                reasons.append(f"Negative 20d momentum: {mom20:+.1f}%")
                flags["weak_momentum"] = True

        # 60-day momentum (informational only, not scored)
        mom60 = history.pct_change(days=min(60, n - 1))
        result.momentum_60d_pct = _r(mom60)

        # ── Volume ratio 20d/60d (max 1 pt) ──────────────────────────────────
        if len(volumes) >= 60:
            avg20 = sum(volumes[-20:]) / 20
            avg60 = sum(volumes[-60:]) / 60
            vol_ratio = avg20 / avg60 if avg60 else 1.0
            result.volume_ratio_20_60 = _r(vol_ratio)
            if vol_ratio > 1.2:
                total_score += 1.0
                reasons.append(f"Rising volume (ratio {vol_ratio:.2f}) — confirms trend")
                flags["volume_surge"] = True
            elif vol_ratio >= 0.8:
                total_score += 0.5
                reasons.append(f"Stable volume (ratio {vol_ratio:.2f})")
            else:
                reasons.append(f"Declining volume (ratio {vol_ratio:.2f})")
                flags["volume_dry"] = True

        # ── 52-week range position (max 2 pts) ────────────────────────────────
        lookback = min(252, n)
        period_closes = closes[-lookback:]
        low52 = min(period_closes)
        high52 = max(period_closes)
        if high52 > low52:
            pos_pct = (price - low52) / (high52 - low52) * 100
            result.week52_position_pct = _r(pos_pct)
            if pos_pct >= 80:
                total_score += 2.0
                reasons.append(f"At {pos_pct:.0f}th pct of {lookback//21}m range — high relative strength")
                flags["near_52w_high"] = pos_pct >= 95
            elif pos_pct >= 50:
                total_score += 1.0
                reasons.append(f"At {pos_pct:.0f}th pct of {lookback//21}m range")
            else:
                reasons.append(f"At {pos_pct:.0f}th pct of {lookback//21}m range — in lower half")
                if pos_pct <= 20:
                    flags["near_52w_low"] = True

        # ── Final signal ──────────────────────────────────────────────────────
        total_score = min(total_score, 10.0)
        if total_score >= 8.0:
            signal = "BUY"
        elif total_score >= 6.0:
            signal = "HOLD"
        elif total_score >= 4.0:
            signal = "WATCH"
        else:
            signal = "AVOID"

        result.score = round(total_score, 2)
        result.signal = signal
        result.reasons = reasons
        result.flags = flags

        logger.debug("TechnicalScore %s: %.1f (%s)", symbol, total_score, signal)
        return result


# ── Pure math helpers ─────────────────────────────────────────────────────────

def _rsi(closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _dma(closes: list[float], period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 4)


def _r(v: Optional[float], decimals: int = 2) -> Optional[float]:
    return round(v, decimals) if v is not None else None
