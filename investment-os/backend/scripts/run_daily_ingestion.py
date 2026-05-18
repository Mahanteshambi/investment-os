"""Daily ingestion script for Investment OS.

Runs the full daily data pipeline:
  1. Macro indicators (DXY, US10Y, Brent) — no auth required
  2. OHLCV prices for all watchlist instruments — Kite primary, yfinance fallback

Run manually:
    cd investment-os/backend
    uv run python scripts/run_daily_ingestion.py

Run with flags:
    uv run python scripts/run_daily_ingestion.py --macro-only
    uv run python scripts/run_daily_ingestion.py --prices-only
    uv run python scripts/run_daily_ingestion.py --symbol NIFTYBEES --token 2707457

Exit codes:
    0  All pipelines completed without errors
    1  One or more pipelines failed
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

# Ensure src/ is on the path when run as a script from the backend root
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from investment_os.core.logging import get_logger
from investment_os.data_layer.ingestion.macro_ingestion import MacroIngestion
from investment_os.data_layer.ingestion.price_ingestion import PriceIngestion

logger = get_logger(__name__)


def run_macro(metrics: list[str] | None = None) -> bool:
    """Run macro ingestion. Returns True on success."""
    logger.info("=" * 50)
    logger.info("STEP 1 — Macro Indicators")
    logger.info("=" * 50)
    result = MacroIngestion().run(metrics=metrics)
    logger.info(result.summary())
    if not result.ok:
        logger.error("Macro ingestion failed: %s", result.error)
    return result.ok


def run_prices(symbol: str | None = None, token: int | None = None) -> bool:
    """Run price ingestion. Returns True if no fatal failures."""
    logger.info("=" * 50)
    logger.info("STEP 2 — OHLCV Prices")
    logger.info("=" * 50)

    ingestion = PriceIngestion()

    if symbol:
        result = ingestion.run_symbol(symbol, token=token)
        ok = result.ok
        logger.info(
            "%s via %s — %d bars (error: %s)",
            result.symbol, result.source, result.bars_fetched, result.error,
        )
    else:
        result = ingestion.run()
        ok = result.failed_count == 0
        logger.info(result.summary())
        if result.failed_count:
            logger.warning(
                "Failed symbols: %s",
                [r.symbol for r in result.symbols if r.error],
            )

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Investment OS daily ingestion pipeline")
    parser.add_argument("--macro-only", action="store_true", help="Run macro ingestion only")
    parser.add_argument("--prices-only", action="store_true", help="Run price ingestion only")
    parser.add_argument("--symbol", type=str, default=None, help="Run for a single NSE symbol")
    parser.add_argument("--token", type=int, default=None, help="Kite instrument token for --symbol")
    parser.add_argument(
        "--metrics", type=str, default=None,
        help="Comma-separated macro metrics (default: DXY,US10Y,BRENT)",
    )
    args = parser.parse_args()

    start = time.monotonic()
    logger.info("Investment OS Daily Ingestion — %s", date.today().isoformat())

    metrics = [m.strip().upper() for m in args.metrics.split(",")] if args.metrics else None
    all_ok = True

    if not args.prices_only:
        all_ok &= run_macro(metrics=metrics)

    if not args.macro_only:
        all_ok &= run_prices(symbol=args.symbol, token=args.token)

    elapsed = time.monotonic() - start
    status = "SUCCESS" if all_ok else "PARTIAL FAILURE"
    logger.info("Ingestion complete [%s] in %.1fs", status, elapsed)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
