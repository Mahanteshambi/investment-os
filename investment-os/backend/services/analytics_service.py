import logging
from datetime import date, datetime
from typing import Optional

from models.schemas import HoldingResponse, PortfolioSummary

logger = logging.getLogger(__name__)


def calculate_portfolio_summary(
    holdings: list[HoldingResponse],
    previous_snapshot=None,
    cash_flows: list[tuple[date, float]] | None = None,
    last_synced: Optional[datetime] = None,
) -> PortfolioSummary:
    total_value = sum(h.current_value or 0 for h in holdings)
    invested_value = sum(h.invested_value or 0 for h in holdings)
    total_pnl = total_value - invested_value
    total_pnl_pct = (total_pnl / invested_value * 100) if invested_value else 0.0

    # Day P&L from previous snapshot
    day_pnl = 0.0
    day_pnl_pct = 0.0
    if previous_snapshot and previous_snapshot.get("total_value"):
        prev_val = float(previous_snapshot["total_value"])
        day_pnl = total_value - prev_val
        day_pnl_pct = (day_pnl / prev_val * 100) if prev_val else 0.0

    # Allocation by asset class
    allocation: dict[str, float] = {}
    if total_value > 0:
        class_totals: dict[str, float] = {}
        for h in holdings:
            cls = h.asset_class
            class_totals[cls] = class_totals.get(cls, 0.0) + (h.current_value or 0)
        allocation = {cls: round(val / total_value * 100, 2) for cls, val in class_totals.items()}

    # XIRR
    xirr: Optional[float] = None
    if cash_flows and len(cash_flows) >= 2:
        xirr = calculate_xirr(cash_flows)

    return PortfolioSummary(
        total_value=total_value,
        invested_value=invested_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        day_pnl=day_pnl,
        day_pnl_pct=day_pnl_pct,
        xirr=xirr,
        allocation=allocation,
        last_synced=last_synced,
    )


def calculate_sector_exposure(holdings: list[HoldingResponse]) -> list[dict]:
    total_value = sum(h.current_value or 0 for h in holdings)
    sector_totals: dict[str, float] = {}
    for h in holdings:
        sector = h.sector or h.asset_class or "Other"
        sector_totals[sector] = sector_totals.get(sector, 0.0) + (h.current_value or 0)

    result = []
    for sector, value in sorted(sector_totals.items(), key=lambda x: -x[1]):
        pct = round(value / total_value * 100, 2) if total_value else 0.0
        result.append({"sector": sector, "value": round(value, 2), "pct": pct})
    return result


def calculate_xirr(cash_flows: list[tuple[date, float]]) -> Optional[float]:
    """
    Standard XIRR via scipy brentq.
    cash_flows: [(date, amount)] — buys are negative, current portfolio value is positive.
    """
    try:
        from scipy.optimize import brentq

        dates = [cf[0] for cf in cash_flows]
        amounts = [cf[1] for cf in cash_flows]
        base_date = dates[0]
        days = [(d - base_date).days for d in dates]

        def npv(rate: float) -> float:
            return sum(
                amt / ((1 + rate) ** (d / 365.0))
                for amt, d in zip(amounts, days)
            )

        result = brentq(npv, -0.999, 100.0, maxiter=1000)
        return round(result * 100, 2)
    except Exception as e:
        logger.warning(f"XIRR calculation failed: {e}")
        return None
