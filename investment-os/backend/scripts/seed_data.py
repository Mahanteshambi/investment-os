from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime, timedelta

from database.connection import get_connection


SAMPLE_HOLDINGS = [
    {
        "asset_name": "Nippon India ETF Nifty BeES",
        "ticker": "NIFTYBEES",
        "asset_class": "equity",
        "sub_class": "large_cap",
        "source": "manual",
        "quantity": 620.0,
        "avg_cost": 236.50,
        "current_price": 254.10,
        "sector": "Index",
    },
    {
        "asset_name": "Nippon India ETF Junior BeES",
        "ticker": "JUNIORBEES",
        "asset_class": "equity",
        "sub_class": "mid_small",
        "source": "manual",
        "quantity": 410.0,
        "avg_cost": 571.80,
        "current_price": 603.20,
        "sector": "Index",
    },
    {
        "asset_name": "Gold BeES",
        "ticker": "GOLDBEES",
        "asset_class": "gold",
        "sub_class": "commodity",
        "source": "manual",
        "quantity": 880.0,
        "avg_cost": 58.40,
        "current_price": 63.70,
        "sector": "Gold",
    },
    {
        "asset_name": "ICICI Prudential US Bluechip",
        "ticker": "ICICIBLUE",
        "asset_class": "mf",
        "sub_class": "international",
        "source": "sheets",
        "quantity": 1240.0,
        "avg_cost": 61.70,
        "current_price": 69.80,
        "sector": "US Equity",
    },
    {
        "asset_name": "Liquid BeES",
        "ticker": "LIQUIDBEES",
        "asset_class": "debt",
        "sub_class": "liquid",
        "source": "manual",
        "quantity": 190.0,
        "avg_cost": 1000.00,
        "current_price": 1005.50,
        "sector": "Debt",
    },
    {
        "asset_name": "Cash Balance",
        "ticker": "CASH",
        "asset_class": "cash",
        "sub_class": "cash",
        "source": "manual",
        "quantity": 1.0,
        "avg_cost": 85000.00,
        "current_price": 85000.00,
        "sector": "Cash",
    },
]


def _calculate_values(holding: dict) -> tuple[float, float, float, float]:
    quantity = float(holding["quantity"])
    avg_cost = float(holding["avg_cost"])
    current_price = float(holding["current_price"])
    invested_value = round(quantity * avg_cost, 2)
    current_value = round(quantity * current_price, 2)
    pnl = round(current_value - invested_value, 2)
    pnl_pct = round((pnl / invested_value) * 100, 2) if invested_value else 0.0
    return invested_value, current_value, pnl, pnl_pct


def seed_holdings(reset: bool) -> int:
    conn = get_connection()
    if reset:
        conn.execute("DELETE FROM holdings")
        conn.execute("DELETE FROM daily_snapshots")
        conn.execute("DELETE FROM sync_log")

    now = datetime.now()
    for h in SAMPLE_HOLDINGS:
        invested_value, current_value, pnl, pnl_pct = _calculate_values(h)
        conn.execute(
            """
            INSERT INTO holdings (
                id, asset_name, ticker, asset_class, sub_class, source,
                quantity, avg_cost, current_price, current_value, invested_value,
                unrealized_pnl, unrealized_pnl_pct, sector, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                h["asset_name"],
                h["ticker"],
                h["asset_class"],
                h["sub_class"],
                h["source"],
                h["quantity"],
                h["avg_cost"],
                h["current_price"],
                current_value,
                invested_value,
                pnl,
                pnl_pct,
                h["sector"],
                now,
            ],
        )

    return len(SAMPLE_HOLDINGS)


def seed_snapshots(days: int = 30) -> int:
    conn = get_connection()
    totals = conn.execute(
        """
        SELECT
            COALESCE(SUM(current_value), 0),
            COALESCE(SUM(invested_value), 0),
            COALESCE(SUM(CASE WHEN asset_class = 'equity' THEN current_value ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN asset_class = 'mf' THEN current_value ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN asset_class = 'gold' THEN current_value ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN asset_class = 'cash' THEN current_value ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN asset_class = 'debt' THEN current_value ELSE 0 END), 0)
        FROM holdings
        """
    ).fetchone()

    total_value, invested_value, equity_value, mf_value, gold_value, cash_value, debt_value = [
        float(v) for v in totals
    ]
    if total_value == 0:
        return 0

    for i in range(days):
        snapshot_day = date.today() - timedelta(days=days - 1 - i)
        trend_multiplier = 0.96 + (i / max(days - 1, 1)) * 0.06
        day_total_value = round(total_value * trend_multiplier, 2)
        day_invested = round(invested_value * (0.98 + (i / max(days - 1, 1)) * 0.02), 2)
        day_total_pnl = round(day_total_value - day_invested, 2)
        day_total_pnl_pct = round((day_total_pnl / day_invested) * 100, 2) if day_invested else 0.0

        conn.execute(
            """
            INSERT OR REPLACE INTO daily_snapshots (
                snapshot_date, total_value, invested_value, total_pnl, total_pnl_pct,
                equity_pct, mf_pct, gold_pct, cash_pct, debt_pct, nifty50_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                snapshot_day,
                day_total_value,
                day_invested,
                day_total_pnl,
                day_total_pnl_pct,
                round((equity_value / total_value) * 100, 2),
                round((mf_value / total_value) * 100, 2),
                round((gold_value / total_value) * 100, 2),
                round((cash_value / total_value) * 100, 2),
                round((debt_value / total_value) * 100, 2),
                round(day_total_value * 0.4, 2),
            ],
        )

    return days


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Investment OS local database with sample data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing holdings/snapshots/sync logs before loading sample data",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of historical daily snapshots to generate",
    )
    args = parser.parse_args()

    seeded_holdings = seed_holdings(reset=args.reset)
    seeded_snapshots = seed_snapshots(days=max(1, args.days))
    print(f"Seeded holdings: {seeded_holdings}")
    print(f"Seeded daily snapshots: {seeded_snapshots}")
    print("Done.")


if __name__ == "__main__":
    main()
