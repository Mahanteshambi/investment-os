# CLAUDE_ANALYSIS_TOOLS.md
> Quick reference for calling `investment_os.tools.analysis_tools` from any Claude skill session.

---

## One-line setup

```bash
cd "/path/to/investment-os/backend"
# Then prefix every Python call with: uv run python -c "..."
```

All tools handle DuckDB lock automatically (read-only when FastAPI server is running).
Ingestion (price writes) requires stopping the server first.

---

## The 4 Tools — Copy-Paste Calls

### 1. Portfolio Snapshot
**When:** Start of every SKILL-02 brief. Replaces manual `portfolio_state.json` read + macro curls.

```bash
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_portfolio_snapshot
print(json.dumps(get_portfolio_snapshot(), indent=2))
"
```

**Key fields to extract:**
```
budget.remaining_inr          → ₹ left this month
budget.trading_days_remaining → days left (triggers final-week rule if ≤ 8)
budget.daily_target_inr       → today's deployment target
budget.available_cash_inr     → settled cash in Kite
macro.DXY / .US10Y / .BRENT   → live macro (no curl needed)
trailing_stops[]               → active stops with stop_price, status
active_sector_etf             → e.g. "CPSEETF"
portfolio.by_asset_class      → allocation breakdown
```

---

### 2. Screen for Buy Candidates
**When:** Step 4 of SKILL-02. Finds instruments below 20-DMA.

```bash
# Weeks 1–3 of month (days 1–21): deploy on dips ≥ 2%
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import screen_undervalued
print(json.dumps(screen_undervalued(min_dip_pct=2.0), indent=2))
"

# Final week (trading_days_remaining ≤ 8): deploy regardless of dip
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import screen_undervalued
print(json.dumps(screen_undervalued(min_dip_pct=0.0), indent=2))
"
```

**Filter the results:**
- Keep: `technical_signal` in `[BUY, HOLD, WATCH]`
- Skip always: `PSUBNKBEES` (stopped May 15 2026), `ITBEES` (exited)
- Prioritise: higher `technical_score`, deeper `dip_pct`, in-budget bucket

---

### 3. Technical Score (per instrument)
**When:** Confirm top 3 candidates from screen. Also used in SKILL-04 to validate scores.

```bash
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_technical_score
print(json.dumps(get_technical_score('NIFTYBEES'), indent=2))
"
```

**Signals:** `BUY` (≥8) · `HOLD` (6–8) · `WATCH` (4–6) · `AVOID` (<4) · `NO_DATA` · `ERROR`

**Key flags to mention in brief:**
```
flags.oversold        → RSI < 30, bounce risk — mention in brief
flags.overbought      → RSI > 75, caution on new entry
flags.above_50dma     → structural support confirmed
flags.below_dma       → weakness, requires FII/DII confirmation
flags.weak_momentum   → negative 20d trend
flags.volume_dry      → distribution pattern
indicators.bars_used  → if < 60, run price ingestion first
```

**Batch call for SKILL-04 (all 12 sector ETFs at once):**
```bash
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_technical_score
sectors = ['CPSEETF','PHARMABEES','MODEFENCE','METALIETF','ENERGY',
           'INFRABEES','AUTOBEES','PSUBNKBEES','MOREALTY','BANKBEES','BFSI','ITBEES']
for s in sectors:
    r = get_technical_score(s)
    print(f\"{s}: score={r['score']} signal={r['signal']} rsi={r['indicators']['rsi14']} bars={r['indicators']['bars_used']}\")
"
```

---

### 4. Sector Rotation Data
**When:** SKILL-02 step 2. SKILL-04 pre-write validation.

```bash
# Standard (reads sector_rotation.json — instant)
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_sector_rotation_data
print(json.dumps(get_sector_rotation_data(), indent=2))
"

# With live DB overlay (adds live RSI/momentum from price DB)
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_sector_rotation_data
print(json.dumps(get_sector_rotation_data(refresh_live=True), indent=2))
"
```

**Key fields:**
```
active_sector_etf          → e.g. "CPSEETF" — use this, not target_allocation.json
rotation_decision          → SKILL-04's narrative
sectors[].decision         → BUY | HOLD | WATCH | AVOID | EXITED | STOPPED
sectors[].monthly_allocation_inr → budget for this sector
sectors[].notes            → SKILL-04 analysis + entry rationale
sectors[].live.*           → only populated with refresh_live=True
```

---

## Error Handling

All tools return a safe dict — they never raise. Check before using:

```python
score = get_technical_score("NIFTYBEES")
if score["signal"] in ("ERROR", "NO_DATA"):
    # bars_used == 0 → price ingestion hasn't run
    # Fall back to sector_rotation.json rsi14/dma_detail for this instrument
    pass
```

---

## Running Ingestion (when price data is stale)

Stop the FastAPI server first, then:

```bash
cd investment-os/backend

# Both macro + prices (full daily run)
uv run python scripts/run_daily_ingestion.py

# Macro only (DXY, US10Y, BRENT) — ~1 second
uv run python scripts/run_daily_ingestion.py --macro-only

# Prices only (14 instruments, ~2 seconds)
uv run python scripts/run_daily_ingestion.py --prices-only

# Single symbol
uv run python scripts/run_daily_ingestion.py --prices-only --symbol CPSEETF
```

Restart server after: `uv run uvicorn main:app --port 8000 --reload &`

---

## Data Freshness Table

| What | Last updated | Stale after | How to refresh |
|------|-------------|-------------|----------------|
| OHLCV prices | Daily ingestion | 1 trading day | `--prices-only` |
| Macro (DXY/US10Y/Brent) | Daily ingestion | 1 day | `--macro-only` |
| Holdings + P&L | Kite sync | After any trade | Kite sync endpoint or manual |
| Sector rotation | SKILL-04 (monthly) | 1 month | SKILL-04 on 1st |
| Fundamentals | Not yet seeded | — | Export Tickertape CSV + run ingestion |

**DMA-200 note:** Seeded from Sep 2025. DMA-200 available ~Sep 2026 (needs 200 bars).
Until then, `dma_200 = null` and technical scores use 50-DMA as long-term reference.

---

## SKILL-02 Step Sequence (with tool integration)

```
1. get_portfolio_snapshot()          → budget, macro, trailing stops, active sector
2. get_sector_rotation_data()        → rotation decision, active ETF, sector notes
3. NSE FII/DII (mcp__shell)          → institutional flows
4. screen_undervalued(dip_pct)       → today's buy candidates
5. get_technical_score(top 3 only)   → confirm entry quality
6. mcp__kite__get_ltp (shortlist)    → live price for GTT calculation
7. Compile brief → print + write daily_signal.json
8. Wait for "confirm" → place GTTs one at a time
```

## SKILL-04 Step Sequence (with tool integration)

```
1. Batch get_technical_score() for all 12 sectors → baseline technical scores
2. NSE FII/DII → institutional score per sector
3. Macro context (from get_portfolio_snapshot macro) → fundamental overlay
4. Score: composite = technical*0.4 + fundamental*0.3 + fii_dii*0.3
5. Apply rotation rule (gap ≥ 1.0 from current active)
6. PRE-WRITE: get_sector_rotation_data(refresh_live=True) → sanity check live RSI/momentum
7. Write sector_rotation.json (current_month + history)
8. Print scorecard table
```
