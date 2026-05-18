"""Claude-callable analysis tools for Investment OS.

Every public function in this module:
  - Takes simple Python primitives as arguments (str, float, int, list, date)
  - Returns a structured dict that Claude can read and reason over directly
  - Is fully self-contained — no caller setup required
  - Logs clearly so failures are diagnosable

All monetary values are in INR.  All percentages are numbers (12.5 = 12.5%).
Scores are 0-10.  Signals use a consistent vocabulary:
  Technical  →  BUY | HOLD | WATCH | AVOID | NO_DATA
  Fundamental → STRONG | GOOD | FAIR | WEAK | NO_DATA
  Combined   →  BUY | HOLD | WATCH | AVOID

──────────────────────────────────────────────────────────────────────────────
TOOL INDEX

  get_technical_score(symbol)               Price-action score + RSI / DMA
  get_fundamental_score(symbol)             Quality + valuation score
  get_composite_score(symbol)               Both scores combined
  get_sector_rotation_data(refresh_live)    Full sector rankings + active ETF
  screen_undervalued(...)                   Find instruments in dip territory
  run_backtest(...)                         SIP backtest on historical prices
  get_portfolio_snapshot()                  Holdings + budget + trailing stops
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Optional

from investment_os.analysis.fundamental_scorer import FundamentalScorer
from investment_os.analysis.sector_scorer import SectorScorer
from investment_os.analysis.technical_scorer import TechnicalScorer
from investment_os.core.logging import get_logger
from investment_os.data_layer.ingestion.macro_ingestion import MacroIngestion
from investment_os.data_layer.loaders.json_state_loader import JsonStateLoader
from investment_os.data_layer.repositories.holdings_repository import HoldingsRepository
from investment_os.data_layer.repositories.price_repository import PriceRepository

logger = get_logger(__name__)

# ── Shared singletons (lazy-init on first call) ───────────────────────────────
_tech_scorer: Optional[TechnicalScorer] = None
_fund_scorer: Optional[FundamentalScorer] = None
_sector_scorer: Optional[SectorScorer] = None
_price_repo: Optional[PriceRepository] = None
_holdings_repo: Optional[HoldingsRepository] = None
_loader: Optional[JsonStateLoader] = None
_macro: Optional[MacroIngestion] = None


def _ts() -> TechnicalScorer:
    global _tech_scorer
    if _tech_scorer is None:
        _tech_scorer = TechnicalScorer()
    return _tech_scorer


def _fs() -> FundamentalScorer:
    global _fund_scorer
    if _fund_scorer is None:
        _fund_scorer = FundamentalScorer()
    return _fund_scorer


def _ss() -> SectorScorer:
    global _sector_scorer
    if _sector_scorer is None:
        _sector_scorer = SectorScorer()
    return _sector_scorer


def _pr() -> PriceRepository:
    global _price_repo
    if _price_repo is None:
        _price_repo = PriceRepository()
    return _price_repo


def _hr() -> HoldingsRepository:
    global _holdings_repo
    if _holdings_repo is None:
        _holdings_repo = HoldingsRepository()
    return _holdings_repo


def _jl() -> JsonStateLoader:
    global _loader
    if _loader is None:
        _loader = JsonStateLoader()
    return _loader


def _safe_call(tool_name: str, fn, *args, **kwargs) -> dict:
    """Call `fn(*args, **kwargs)` and return its result.

    On any exception, log the error and return a safe error dict so one
    failing tool never propagates an exception to the caller.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.error("%s failed: %s", tool_name, exc, exc_info=True)
        return {
            "tool": tool_name,
            "signal": "ERROR",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


def _mi() -> MacroIngestion:
    global _macro
    if _macro is None:
        _macro = MacroIngestion()
    return _macro


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 1 — get_technical_score
# ──────────────────────────────────────────────────────────────────────────────

def get_technical_score(symbol: str) -> dict[str, Any]:
    """Return the technical analysis score for an NSE instrument.

    Uses stored OHLCV bars (run price ingestion first).  No live network call.

    Args:
        symbol: Bare NSE symbol, e.g. "NIFTYBEES", "GOLDBEES", "CPSEETF".

    Returns:
        {
          "symbol": str,
          "score": float (0-10),
          "signal": "BUY" | "HOLD" | "WATCH" | "AVOID" | "NO_DATA",
          "reasons": list[str],        # human-readable scoring rationale
          "flags": dict[str, bool],    # notable conditions (overbought, etc.)
          "indicators": {
            "current_price": float,
            "rsi14": float,
            "dma_20": float, "dma_50": float, "dma_200": float,
            "momentum_20d_pct": float,
            "momentum_60d_pct": float,
            "volume_ratio_20_60": float,
            "week52_position_pct": float,
            "bars_used": int,
          }
        }

    Example:
        >>> get_technical_score("NIFTYBEES")
        {"symbol": "NIFTYBEES", "score": 8.5, "signal": "BUY", ...}
    """
    sym = symbol.upper().strip()
    return _safe_call("get_technical_score", lambda: _ts().score(sym).as_dict())


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 2 — get_fundamental_score
# ──────────────────────────────────────────────────────────────────────────────

def get_fundamental_score(symbol: str) -> dict[str, Any]:
    """Return the fundamental quality + valuation score for an instrument.

    Uses data stored in the `fundamentals` table (requires Tickertape CSV import).
    ETFs score on a relaxed rubric (PE not penalised).

    Args:
        symbol: Bare NSE symbol or company ticker.

    Returns:
        {
          "symbol": str,
          "score": float (0-10),
          "signal": "STRONG" | "GOOD" | "FAIR" | "WEAK" | "NO_DATA",
          "period": {"type": str, "end": str, "source": str},
          "reasons": list[str],
          "flags": dict[str, bool],   # high_roce, high_debt, loss_making, etc.
          "metrics": {
            "roce_pct", "roe_pct", "debt_to_equity",
            "pe_ratio", "pb_ratio",
            "profit_growth_1y_pct", "revenue_growth_1y_pct",
            "promoter_holding_pct"
          }
        }
    """
    sym = symbol.upper().strip()
    return _safe_call("get_fundamental_score", lambda: _fs().score(sym).as_dict())


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 3 — get_composite_score
# ──────────────────────────────────────────────────────────────────────────────

def get_composite_score(symbol: str) -> dict[str, Any]:
    """Return combined technical + fundamental score with a unified signal.

    Weights: technical 60%, fundamental 40%.
    If fundamental data is missing, falls back to technical score only.

    Args:
        symbol: Bare NSE symbol.

    Returns:
        {
          "symbol": str,
          "composite_score": float (0-10),
          "signal": "BUY" | "HOLD" | "WATCH" | "AVOID",
          "technical": { ... },     # full technical score dict
          "fundamental": { ... },   # full fundamental score dict
          "summary": str,           # one-line Claude-readable verdict
        }

    Example:
        >>> get_composite_score("CPSEETF")
        {"symbol": "CPSEETF", "composite_score": 8.1, "signal": "BUY", ...}
    """
    sym = symbol.upper().strip()
    try:
        tech = _ts().score(sym)
        fund = _fs().score(sym)

        has_fund = fund.signal != "NO_DATA"

        if has_fund:
            composite = round(tech.score * 0.6 + fund.score * 0.4, 2)
        else:
            composite = tech.score

        if composite >= 8.0:
            signal = "BUY"
        elif composite >= 6.0:
            signal = "HOLD"
        elif composite >= 4.0:
            signal = "WATCH"
        else:
            signal = "AVOID"

        fund_note = (
            f"fundamental {fund.score:.1f}/10 ({fund.signal})"
            if has_fund else "no fundamental data"
        )
        summary = (
            f"{sym}: composite {composite:.1f}/10 → {signal}. "
            f"Technical {tech.score:.1f}/10 ({tech.signal}), {fund_note}."
        )

        return {
            "symbol": sym,
            "composite_score": composite,
            "signal": signal,
            "summary": summary,
            "weights": {"technical": 0.6 if has_fund else 1.0, "fundamental": 0.4 if has_fund else 0.0},
            "technical": tech.as_dict(),
            "fundamental": fund.as_dict(),
        }
    except Exception as exc:
        logger.error("get_composite_score(%s) failed: %s", sym, exc)
        return _error_dict(sym, str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 4 — get_sector_rotation_data
# ──────────────────────────────────────────────────────────────────────────────

def get_sector_rotation_data(refresh_live: bool = False) -> dict[str, Any]:
    """Return the current sector rotation rankings and active ETF.

    Reads from sector_rotation.json (SKILL-04 output).  Optionally overlays
    live RSI and momentum from stored OHLCV bars.

    Args:
        refresh_live: If True, overlay fresh technical indicators from DB.

    Returns:
        {
          "month": str,
          "generated_date": str,
          "active_sector_etf": str,        # e.g. "CPSEETF"
          "active_sector_score": float,
          "rotation_decision": str,
          "sectors": [
            {
              "rank": int,
              "sector": str,
              "etf": str,
              "kite_token": int,
              "scores": {"composite", "technical", "fundamental", "fii_dii"},
              "decision": "BUY" | "HOLD" | "WATCH" | "AVOID" | "STOPPED",
              "monthly_allocation_inr": float,
              "current_price": float,
              "rsi14": float,
              "notes": str,
              "live": {...}              # present only when refresh_live=True
            }, ...
          ],
          "history_months_available": list[str]
        }
    """
    return _safe_call(
        "get_sector_rotation_data",
        lambda: _ss().get_current_data(refresh_live=refresh_live).as_dict(),
    )


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 5 — screen_undervalued
# ──────────────────────────────────────────────────────────────────────────────

def screen_undervalued(
    min_dip_pct: float = 2.0,
    max_pe: Optional[float] = None,
    min_roce_pct: Optional[float] = None,
    asset_classes: Optional[list[str]] = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Find watchlist instruments currently in dip territory.

    A "dip" is defined as current price being `min_dip_pct`% below the
    20-day moving average — consistent with the investment strategy rules.

    Args:
        min_dip_pct:   Minimum % below 20-DMA to qualify (default 2.0).
        max_pe:        Filter out instruments with PE above this (None = no filter).
        min_roce_pct:  Filter out instruments with ROCE below this (None = no filter).
        asset_classes: Limit to specific asset classes ["etf", "equity", ...].
                       None = include all.
        limit:         Maximum results to return.

    Returns:
        {
          "screen_date": str,
          "criteria": {"min_dip_pct", "max_pe", "min_roce_pct"},
          "candidates": [
            {
              "symbol": str,
              "current_price": float,
              "dma_20": float,
              "dip_pct": float,          # negative = below DMA (bigger = bigger dip)
              "technical_signal": str,
              "technical_score": float,
              "fundamental_signal": str,
              "recommendation": str,     # Claude-readable one-liner
            }, ...
          ],
          "count": int,
          "note": str
        }
    """
    try:
        targets = _jl().get_ingest_targets()
        if asset_classes:
            cls_set = {c.lower() for c in asset_classes}

        candidates = []
        for inst in targets:
            sym = inst.symbol
            history = _pr().get_bars(
                sym, from_date=date.today() - timedelta(days=40)
            )
            if len(history) < 20:
                continue

            closes = history.closes()
            price = closes[-1]
            dma20 = sum(closes[-20:]) / 20
            dip_pct = (dma20 - price) / dma20 * 100  # positive = below DMA

            if dip_pct < min_dip_pct:
                continue

            tech = _ts().score(sym)
            fund = _fs().score(sym)

            if max_pe and fund.pe_ratio and fund.pe_ratio > max_pe:
                continue
            if min_roce_pct and fund.roce_pct is not None and fund.roce_pct < min_roce_pct:
                continue

            rec = (
                f"{sym} is {dip_pct:.1f}% below 20-DMA at ₹{price:.2f} "
                f"(DMA ₹{dma20:.2f}). Technical: {tech.signal} ({tech.score:.1f}). "
                f"Fundamental: {fund.signal}."
            )

            candidates.append({
                "symbol": sym,
                "bucket": inst.bucket,
                "current_price": round(price, 2),
                "dma_20": round(dma20, 2),
                "dip_pct": round(dip_pct, 2),
                "technical_signal": tech.signal,
                "technical_score": tech.score,
                "rsi14": tech.rsi14,
                "fundamental_signal": fund.signal,
                "fundamental_score": fund.score,
                "recommendation": rec,
            })

        # Sort by dip_pct descending (biggest dip first) then by tech score desc
        candidates.sort(key=lambda x: (-x["dip_pct"], -x["technical_score"]))
        candidates = candidates[:limit]

        note = (
            f"Strategy rule: deploy if instrument is >{min_dip_pct}% below 20-DMA "
            f"(weeks 1-3 of month). Final week: deploy regardless of dip."
        )

        return {
            "screen_date": str(date.today()),
            "criteria": {
                "min_dip_pct": min_dip_pct,
                "max_pe": max_pe,
                "min_roce_pct": min_roce_pct,
                "asset_classes": asset_classes,
            },
            "candidates": candidates,
            "count": len(candidates),
            "note": note,
        }

    except Exception as exc:
        logger.error("screen_undervalued failed: %s", exc, exc_info=True)
        return {"error": str(exc), "error_type": type(exc).__name__, "candidates": [], "count": 0}


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 6 — run_backtest
# ──────────────────────────────────────────────────────────────────────────────

def run_backtest(
    symbol: str,
    monthly_amount_inr: float = 10_000,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    buy_day: int = 1,
) -> dict[str, Any]:
    """Run a simple SIP (monthly lump-sum) backtest on stored price history.

    Simulates investing `monthly_amount_inr` on the first available trading
    day on or after `buy_day` of each month.

    Args:
        symbol:              Bare NSE symbol (e.g. "NIFTYBEES").
        monthly_amount_inr:  Fixed monthly investment amount in INR.
        from_date:           Start date "YYYY-MM-DD" (default: earliest bar in DB).
        to_date:             End date "YYYY-MM-DD" (default: latest bar in DB).
        buy_day:             Target day of month for purchase (default 1).

    Returns:
        {
          "symbol": str,
          "period": {"from": str, "to": str, "months": int},
          "investment": {
            "monthly_inr": float,
            "total_invested_inr": float,
            "total_units": float,
            "final_value_inr": float,
            "absolute_return_inr": float,
            "absolute_return_pct": float,
            "cagr_pct": float,
          },
          "trades": list[{"date", "price", "units", "amount"}],
          "note": str
        }
    """
    sym = symbol.upper().strip()
    try:
        start = date.fromisoformat(from_date) if from_date else date.today() - timedelta(days=1825)
        end = date.fromisoformat(to_date) if to_date else date.today()

        history = _pr().get_bars(sym, from_date=start, to_date=end)
        if len(history) < 2:
            return {
                "symbol": sym, "error": f"Only {len(history)} bars available — run price ingestion first",
            }

        # Build (date → close) lookup
        price_map: dict[date, float] = {b.date: b.close for b in history.bars}
        sorted_dates = sorted(price_map)

        # Group trading days by (year, month)
        from collections import defaultdict
        month_days: dict[tuple, list[date]] = defaultdict(list)
        for d in sorted_dates:
            month_days[(d.year, d.month)].append(d)

        trades = []
        total_units = 0.0
        total_invested = 0.0

        for ym in sorted(month_days):
            days = month_days[ym]
            # First trading day >= buy_day; fallback to first available day
            buy_candidates = [d for d in days if d.day >= buy_day]
            trade_date = buy_candidates[0] if buy_candidates else days[0]
            price = price_map[trade_date]
            units = monthly_amount_inr / price
            total_units += units
            total_invested += monthly_amount_inr
            trades.append({
                "date": str(trade_date),
                "price": round(price, 2),
                "units": round(units, 4),
                "amount_inr": monthly_amount_inr,
            })

        final_price = history.latest_close or 0.0
        final_value = total_units * final_price
        abs_return = final_value - total_invested
        abs_return_pct = abs_return / total_invested * 100 if total_invested else 0

        # CAGR: (final/invested)^(1/years) - 1
        years = max((end - start).days / 365.25, 0.1)
        cagr = (((final_value / total_invested) ** (1 / years)) - 1) * 100 if total_invested > 0 else 0

        months = len(trades)

        return {
            "symbol": sym,
            "period": {
                "from": str(sorted_dates[0]),
                "to": str(sorted_dates[-1]),
                "months": months,
            },
            "investment": {
                "monthly_inr": monthly_amount_inr,
                "total_invested_inr": round(total_invested, 2),
                "total_units": round(total_units, 4),
                "final_price": round(final_price, 2),
                "final_value_inr": round(final_value, 2),
                "absolute_return_inr": round(abs_return, 2),
                "absolute_return_pct": round(abs_return_pct, 2),
                "cagr_pct": round(cagr, 2),
            },
            "trades_count": months,
            "trades": trades,
            "note": (
                f"SIP backtest: ₹{monthly_amount_inr:,.0f}/month in {sym} "
                f"over {months} months → CAGR {cagr:.1f}%"
            ),
        }

    except Exception as exc:
        logger.error("run_backtest(%s) failed: %s", sym, exc, exc_info=True)
        return {"symbol": sym, "error": str(exc), "error_type": type(exc).__name__}


# ──────────────────────────────────────────────────────────────────────────────
# TOOL 7 — get_portfolio_snapshot
# ──────────────────────────────────────────────────────────────────────────────

def get_portfolio_snapshot() -> dict[str, Any]:
    """Return a full portfolio snapshot for Claude decision-making.

    Combines:
    - Live holdings from DuckDB (last sync from Kite/Sheets)
    - Budget state from portfolio_state.json
    - Trailing stops from portfolio_state.json
    - Latest macro indicators from macro_data table

    Returns:
        {
          "as_of": str,
          "portfolio": {
            "total_value_inr": float,
            "total_invested_inr": float,
            "total_pnl_inr": float,
            "total_pnl_pct": float,
            "holdings": [ {"symbol", "asset_class", "bucket", "quantity",
                           "avg_cost", "current_price", "current_value",
                           "unrealized_pnl", "unrealized_pnl_pct"}, ... ]
            "by_asset_class": { "etf": float, "equity": float, ... }
          },
          "budget": {
            "month": str,
            "total_inr": float,
            "deployed_inr": float,
            "remaining_inr": float,
            "trading_days_remaining": int,
            "daily_target_inr": float,
            "available_cash_inr": float,
          },
          "trailing_stops": [
            {"symbol", "stop_price", "peak_price", "buffer_pct", "status"}
          ],
          "macro": { "DXY": float, "US10Y": float, "BRENT": float },
          "active_sector_etf": str,
          "note": str
        }
    """
    try:
        holdings = _hr().get_all()
        total_value = sum(h.current_value for h in holdings)
        total_invested = sum(h.invested_value for h in holdings)
        total_pnl = total_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

        by_class: dict[str, float] = {}
        for h in holdings:
            ac = h.asset_class if isinstance(h.asset_class, str) else h.asset_class.value
            by_class[ac] = by_class.get(ac, 0.0) + h.current_value

        holdings_list = [
            {
                "symbol": h.ticker or h.asset_name,
                "asset_name": h.asset_name,
                "asset_class": h.asset_class if isinstance(h.asset_class, str) else h.asset_class.value,
                "sub_class": h.sub_class,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "current_price": h.current_price,
                "current_value_inr": round(h.current_value, 2),
                "unrealized_pnl_inr": round(h.unrealized_pnl, 2),
                "unrealized_pnl_pct": round(h.unrealized_pnl_pct, 2),
            }
            for h in sorted(holdings, key=lambda x: x.current_value, reverse=True)
        ]

        # Budget from JSON
        state = _jl().load_portfolio_state()
        td = state.trading_days_remaining or 1
        daily_target = round(state.remaining_inr / td, 0) if td > 0 else 0

        # Trailing stops
        stops = [
            {
                "symbol": s.symbol,
                "stop_price": s.stop_price,
                "peak_price": s.peak_price,
                "buffer_pct": s.buffer_pct,
                "status": s.status,
            }
            for s in state.trailing_stops
        ]

        # Macro from DB
        macro = _mi().get_latest_from_db()

        # Active sector from sector_rotation.json
        active_sector = _ss().get_active_sector_etf()

        note = (
            f"Holdings as of last Kite sync. "
            f"Budget: ₹{state.remaining_inr:,.0f} remaining of ₹{state.total_budget_inr:,.0f} "
            f"({state.trading_days_remaining} trading days left). "
            f"Active sector: {active_sector}."
        )

        return {
            "as_of": str(date.today()),
            "portfolio": {
                "total_value_inr": round(total_value, 2),
                "total_invested_inr": round(total_invested, 2),
                "total_pnl_inr": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "holdings_count": len(holdings),
                "holdings": holdings_list,
                "by_asset_class": {k: round(v, 2) for k, v in by_class.items()},
            },
            "budget": {
                "month": state.month,
                "total_inr": state.total_budget_inr,
                "deployed_inr": state.deployed_inr,
                "remaining_inr": state.remaining_inr,
                "trading_days_remaining": state.trading_days_remaining,
                "daily_target_inr": daily_target,
                "available_cash_inr": state.available_cash_inr,
            },
            "trailing_stops": stops,
            "macro": macro,
            "active_sector_etf": active_sector,
            "note": note,
        }

    except Exception as exc:
        logger.error("get_portfolio_snapshot failed: %s", exc, exc_info=True)
        return {"error": str(exc), "error_type": type(exc).__name__}


# ── Helper ────────────────────────────────────────────────────────────────────

def _error_dict(symbol: str, error: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "score": 0.0,
        "signal": "ERROR",
        "error": error,
        "reasons": [f"Tool failed: {error}"],
        "flags": {},
    }
