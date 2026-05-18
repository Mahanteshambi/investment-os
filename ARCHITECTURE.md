# Investment OS — Architecture

> Claude is the brain. Mahantesh is the executor.
> Goal: Long-term wealth building via ETF-first, platform-agnostic investing.
> Budget: ₹4L/month. Horizon: 5–10 years. Style: Dip-buying + sector rotation + disciplined exit.

---

## Design Principles

1. **Advisory only** — Claude recommends, never executes
2. **Platform agnostic** — recommendations span Kite, Coin, Vested, INDMoney, FD
3. **Daily cadence** — morning brief every weekday keeps pacing on track
4. **Sector rotation wired in** — monthly scoring drives the 15% sectoral bucket
5. **Exit is first-class** — trailing stops and sector score exits are tracked daily
6. **Execution confirmation loop** — Mahantesh confirms what he did, Claude updates state

---

## Data Flow

```
                    ┌─────────────────────────────────┐
                    │   1st of Month — SKILL-04        │
                    │   Sector Rotation Analyst        │
                    │   → sector_rotation.json         │
                    │   → watchlist.json updated       │
                    └────────────┬────────────────────┘
                                 │ feeds active sector
                                 ▼
          ┌──────────────────────────────────────────────────┐
          │   Every Weekday 8:00 AM — SKILL-02               │
          │   Daily Morning Brief                            │
          │                                                  │
          │   Inputs:                                        │
          │   • NSE FII/DII API (institutional flows)        │
          │   • Kite historical data (price, volume, DMA)    │
          │   • sector_rotation.json (active sector + score) │
          │   • portfolio_state.json (budget, trailing stops)│
          │   • approved_instruments.json (whitelist)        │
          │   • Global cues (Nasdaq, S&P, USD/INR, Oil)      │
          │                                                  │
          │   Agents spawned:                                │
          │   • AGENT-02: technical-analyst (per instrument) │
          │   • AGENT-04: macro-analyst (global + India)     │
          │                                                  │
          │   Outputs:                                       │
          │   • daily_signal.json                           │
          │   • Printed Morning Brief (see format below)    │
          └──────────────────────────────────────────────────┘
                                 │
                                 ▼
          ┌──────────────────────────────────────────────────┐
          │   Mahantesh reads brief, executes on platforms   │
          │   Confirms back: "Executed X units of Y @ ₹Z"   │
          └──────────────────────────────────────────────────┘
                                 │
                                 ▼
          ┌──────────────────────────────────────────────────┐
          │   Claude updates state files                     │
          │   • portfolio_state.json (budget tracker)        │
          │   • paper_trades.json (execution log)            │
          └──────────────────────────────────────────────────┘
```

---

## SKILL-01: `portfolio-architect`
**Trigger:** Manual — run once now, re-run after major life event
**Purpose:** Establish baseline, identify gaps, create first month's plan

```
INPUTS:
  - Google Drive: Ambi Portfolio sheet (id: [google_sheet_id from user_config.json])
  - Kite: get_holdings (current Kite positions)
  - target_allocation.json

STEPS:
  1. Read full portfolio from Drive: FD, MF, Stocks, PPF, PF, Savings, US Stocks (all platforms)
  2. Read Kite holdings
  3. Compute current allocation % across all buckets including non-Kite assets
  4. Compare vs target_allocation.json
  5. Identify gaps per bucket
  6. Produce:
     a. Current vs target allocation table (all assets, all platforms)
     b. Gap analysis: which buckets are under/overweight
     c. First month ₹4L deployment plan — specific instruments, quantities, platforms
     d. FD rotation roadmap: which FDs mature when, where to redirect proceeds
     e. Suggested changes to watchlist.json

OUTPUTS:
  - portfolio_state.json (allocation_snapshot updated)
  - watchlist.json (finalised)
  - Print: full readable summary with actionable first-month plan
```

---

## SKILL-02: `daily-morning-brief`
**Trigger:** Every weekday 8:00 AM
**Purpose:** Single daily recommendation covering all platforms — what to buy, sell, hold today

```
INPUTS — fetch in this order, one at a time:

  STEP 1 — Portfolio snapshot (replaces manual portfolio_state.json read + macro curls)
    Run in investment-os/backend:
      uv run python -c "
      import sys; sys.path.insert(0,'src')
      from investment_os.tools.analysis_tools import get_portfolio_snapshot
      import json; print(json.dumps(get_portfolio_snapshot()))
      "
    Extract from result:
      budget.*           → remaining_inr, trading_days_remaining, daily_target_inr, available_cash_inr
      macro.*            → DXY, US10Y, BRENT (no curl needed)
      trailing_stops[]   → active stops with stop_price, peak_price, status
      active_sector_etf  → current active sector symbol

  STEP 2 — Sector rotation (replaces manual sector_rotation.json read)
    Run:
      uv run python -c "
      import sys; sys.path.insert(0,'src')
      from investment_os.tools.analysis_tools import get_sector_rotation_data
      import json; print(json.dumps(get_sector_rotation_data()))
      "
    Extract: rotation_decision, sectors[0] (active), sectors where decision==BUY

  STEP 3 — NSE FII/DII (still needed — not in DB yet)
    mcp__shell__run_command with NSE API call
    Extract: fii_net_inr, dii_net_inr, stance

  STEP 4 — Screen for today's dip candidates
    Run:
      # Weeks 1–21 of month: dip ≥ 2%
      # Final 8 trading days (day_of_month ≥ 22 OR trading_days_remaining ≤ 8): dip = 0
      uv run python -c "
      import sys; sys.path.insert(0,'src')
      from investment_os.tools.analysis_tools import screen_undervalued
      import json; print(json.dumps(screen_undervalued(min_dip_pct=2.0)))
      "
    Filter candidates: keep technical_signal in (BUY, HOLD, WATCH)
    Exclude: PSUBNKBEES (stopped May 15 2026), ITBEES (exited)

  STEP 5 — Technical confirmation for top 3 candidates only
    For each shortlisted candidate:
      uv run python -c "
      import sys; sys.path.insert(0,'src')
      from investment_os.tools.analysis_tools import get_technical_score
      import json; print(json.dumps(get_technical_score('SYMBOL')))
      "
    Use: flags.oversold (bounce risk), indicators.rsi14, indicators.momentum_20d_pct

  STEP 6 — Kite LTP for confirmation prices
    mcp__kite__get_ltp for final price validation before GTT calculation

ANALYSIS:
  Sector allocation rule (from sector_rotation.json):
    - Active sector score ≥ 7: full ₹60,000 → active sector ETF
    - Score 5–6: ₹30,000 → sector ETF + ₹30,000 → NIFTYBEES
    - Score < 5: skip sector ETF → redirect ₹60,000 → Large Cap

  Trailing stop checks (from get_portfolio_snapshot() trailing_stops[]):
    - If current LTP ≤ stop_price → EXIT recommendation + LTCG/STCG note
    - Status already contains resolution if stopped out

  Budget pacing (from get_portfolio_snapshot() budget.*):
    - If trading_days_remaining ≤ 8 → final-week rule: deploy regardless of dip
    - daily_target_inr already computed — use it directly

OUTPUTS:
  - daily_signal.json (structured recommendations)
  - Printed Morning Brief (see format below)

MORNING BRIEF FORMAT:
========= INVESTMENT BRIEF — [Weekday Date] =========

MARKET PULSE
  FII: [BUYER/SELLER] ₹X Cr  |  DII: [BUYER/SELLER] ₹X Cr
  Nifty: [+/-X%] from yesterday  |  Nasdaq: [+/-X%] overnight
  USD/INR: [rate]  |  Gold: [direction]
  Mood: [1-line interpretation]

BUDGET STATUS
  Month: [deployed] of ₹4,00,000 deployed  |  Remaining: ₹X
  Trading days left: X  |  Daily pacing target: ₹X
  [⚠ BEHIND PACE — deploy ₹X today to stay on track] (if applicable)

TODAY'S ACTIONS

  BUY ────────────────────────────────────────────────
  [For each buy recommendation:]
  [N]. [INSTRUMENT] — [X] units @ ~₹[price] = ₹[total]
       Platform: [Kite/Coin/Vested/INDMoney]
       Bucket: [bucket name] | Monthly bucket deployed: ₹X of ₹X
       Why: [1-2 line reason: dip %, FII/DII signal, technical trigger]
       [If Coin MF]: SIP amount ₹X to [Fund Name]

  HOLD ───────────────────────────────────────────────
  [Instruments to hold and why — 1 line each]

  EXIT / REDUCE ──────────────────────────────────────
  [If any]: [INSTRUMENT] — [reason: trailing stop hit / sector score / rebalancing]
            Platform: [X] | Tax note: [STCG/LTCG, holding period]
            Suggested: Rotate proceeds into [instrument]

  GLOBAL MARKETS ─────────────────────────────────────
  [US/international recommendation if applicable]
  [Vested/INDMoney action if any]

TRAILING STOPS (active positions)
  [Instrument] | Entry: ₹X | Current: ₹X | Stop: ₹X | P&L: +X%
=====================================================
```

---

## SKILL-04: `sector-rotation-analyst`
**Trigger:** 1st of every month at 8:00 AM (if holiday, next trading day)
**Purpose:** Score all sectors, decide active sector ETF for the month, check exits

```
12-SECTOR UNIVERSE (as of May 2026):
  Symbol       Token       Sector
  CPSEETF      595969      PSU/CPSE (NTPC, ONGC, OIL India, Coal India, BEL)
  PHARMABEES   1273089     Pharma
  MODEFENCE    6385665     Defence
  METALIETF    6364417     Metal
  ENERGY       194503681   Energy/Oil & Gas (listed Nov 2025 — <200 candles)
  INFRABEES    5138433     Infrastructure
  AUTOBEES     2017281     Auto
  PSUBNKBEES   3848193     PSU Banking
  MOREALTY     5935105     Realty
  BANKBEES     2928385     Banking (private + public)
  BFSI         1336321     BFSI (broad financials)
  ITBEES       4885505     IT

DATA FETCH (per sector):

  STEP 1 — Pre-computed technical scores (saves 12 Kite API calls)
    Run once for all sector ETFs:
      uv run python -c "
      import sys; sys.path.insert(0,'src')
      from investment_os.tools.analysis_tools import get_technical_score
      import json
      for sym in ['CPSEETF','PHARMABEES','MODEFENCE','METALIETF','ENERGY',
                  'INFRABEES','AUTOBEES','PSUBNKBEES','MOREALTY','BANKBEES','BFSI','ITBEES']:
          print(sym, json.dumps(get_technical_score(sym)))
      "
    Each result gives: score (0–10), rsi14, dma_20/50/200, momentum_20d_pct,
    volume_ratio_20_60, week52_position_pct, flags

    Use these as your technical_score baseline. Override only if:
      - bars_used < 60 (run price ingestion first: run_daily_ingestion.py --prices-only)
      - signal == NO_DATA
      - You have conflicting Kite data from a manual OHLCV check

  STEP 2 — Kite OHLCV (only if tool returns NO_DATA or bars_used < 60)
    mcp__kite__get_historical_data(
      instrument_token = <token above>,
      from_date = "YYYY-MM-DD 09:15:00",   # ~13 months back for 200-DMA headroom
      to_date   = "YYYY-MM-DD 15:30:00",   # today
      interval  = "day"
    )
    Extract: closes[], volumes[]

  NOTE: DMA-200 unavailable until Sep 2026 (need 200 bars; currently 167 seeded).
        Tool uses 50-DMA as long-term reference in the interim. Manual DMA-200
        calculation via Kite data is the override path when precision matters.

TECHNICAL SCORE (40% weight, max 10):
  Use get_technical_score() result directly when bars_used ≥ 60.
  The scoring components below document what the tool computes:

  Component 1 — Price vs 200-DMA (max 3.0):
    200-DMA = mean(last 200 closes). Skip if <200 candles → score 1.5 (neutral)
    vs200 = (current_price / 200dma - 1) * 100
    vs200 ≥ +5%  → 3.0
    vs200 +2–5%  → 2.5
    vs200 0–+2%  → 2.0
    vs200 -2–0%  → 1.0
    vs200 -5–-2% → 0.5
    vs200 < -5%  → 0.0

  Component 2 — Price vs 50-DMA (max 2.0):
    50-DMA = mean(last 50 closes)
    vs50 ≥ +2%   → 2.0
    vs50 0–+2%   → 1.5
    vs50 -2–0%   → 0.5
    vs50 < -2%   → 0.0

  Component 3 — RSI-14 (max 2.0):
    Use Wilder's RSI (exponential smoothing, NOT simple avg):
      gains[i] = max(close[i] - close[i-1], 0)
      losses[i] = max(close[i-1] - close[i], 0)
      seed avg_gain = mean(gains[:14]), avg_loss = mean(losses[:14])
      then: avg_gain = (avg_gain * 13 + gains[i]) / 14  (for i=14 onward)
      RSI = 100 - 100 / (1 + avg_gain / avg_loss)
    RSI ≥ 70     → 2.0
    RSI 60–70    → 2.0
    RSI 50–60    → 1.5
    RSI 40–50    → 1.0
    RSI 30–40    → 0.5
    RSI < 30     → 0.0

  Component 4 — 52-week position % (max 2.0):
    Uses last 252 trading days (or all available if <252)
    pos = (current - low_252) / (high_252 - low_252) * 100
    pos ≥ 80%   → 2.0
    pos 60–80%  → 1.5
    pos 40–60%  → 1.0
    pos 25–40%  → 0.5
    pos < 25%   → 0.0

  Component 5 — Volume ratio 20d/60d (max 1.0):
    ratio = mean(last 20 volumes) / mean(last 60 volumes)
    ratio ≥ 1.2  → 1.0
    ratio 0.8–1.2 → 0.5
    ratio < 0.8  → 0.0

  technical_score = sum of 5 components (max 10.0)

FUNDAMENTAL SCORE (30% weight, max 10):
  Qualitative overlay — assess each sector against current macro:
  Key macro inputs (fetch or use latest known values):
    - DXY: <100 = bullish EM/real assets; >100 = headwind
    - Brent crude: >$90 = bad for consumption/autos, good for E&P (CPSEETF/ENERGY)
    - CAPE ratio: >30 = elevated, favour value sectors
    - RBI policy: rate cut cycle = banking positive; tightening = banking negative
  Sector-specific: PE vs history, earnings trend, policy tailwinds (PLI, budget, capex)
  Score 1–10 using judgement.

FII/DII SCORE (30% weight, max 10):
  Inputs: NSE FII/DII data (https://www.nseindia.com/api/fiidiiTradeReact)
  Both buying = 9–10; one buying = 6–7; both selling = 2–3
  Apply sector preference (FII favours pharma/IT/banks; DII favours domestic)
  Score 1–10.

COMPOSITE SCORE = technical*0.4 + fundamental*0.3 + fii_dii*0.3

DECISION THRESHOLDS:
  composite ≥ 7.0 → BUY  — full ₹60,000/month if active sector
  composite 5–6.9 → HOLD — ₹30,000/month, balance to Large Cap
  composite < 5.0 → AVOID — ₹0, redirect entirely to Large Cap

ROTATION RULE:
  Rotate active sector when: top-ranked sector score exceeds current active by ≥1.0 point
  Do NOT rotate on a 0.2–0.5 point gap — requires clear leadership change

EXIT CHECKS:
  - Any sector with score < 4 for 2 consecutive months → stop new buys + trailing stop exit
  - Track consecutive_below4 via history[].below4_sectors[] array in sector_rotation.json
  - Any sector ETF position with >15% gain → set trailing stop at peak - 8%

PRE-WRITE VALIDATION (before updating sector_rotation.json):
  Run live overlay to cross-check your hand-scored technicals:
    uv run python -c "
    import sys; sys.path.insert(0,'src')
    from investment_os.tools.analysis_tools import get_sector_rotation_data
    import json; print(json.dumps(get_sector_rotation_data(refresh_live=True)))
    "
  For each sector where live.rsi differs from your rsi14 by > 5 points:
    → Recheck your manual calculation
  For each sector where live.momentum_20d_pct contradicts your technical_score:
    → Add a note in the sector's "notes" field explaining the discrepancy

OUTPUTS:
  - sector_rotation.json (update current_month{} with all 12 scores, append compact entry to history[])
  - watchlist.json updated (active sector ETF marked)
  - Print: Sector Scorecard table + rotation recommendation
```

---

## SKILL-05: `quarterly-rebalancer`
**Trigger:** 1st Jan, Apr, Jul, Oct at 8:00 AM
**Purpose:** Check allocation drift, recommend corrections

```
STEPS:
  1. Read target_allocation.json
  2. Fetch Kite holdings via get_holdings
  3. Read Google Drive Ambi Portfolio sheet for non-Kite assets
  4. Compute current % per bucket across ALL assets
  5. Flag any bucket > target ± 5%
  6. For overweight buckets:
     - If gain > 0: recommend trim, state LTCG/STCG implication
     - If at loss: never sell, just stop new buys in that bucket
  7. For underweight buckets: prioritise in next month's daily briefs
  8. Spawn AGENT-03 for optimal rebalancing quantities

OUTPUTS:
  - rebalancing_report.json
  - Print: Drift table + specific rebalancing recommendations with tax notes
  NOTE: Never execute anything — Mahantesh decides and executes
```

---

## SKILL-06: `portfolio-dashboard`
**Trigger:** Every Sunday 9:00 AM
**Purpose:** Weekly health check — P&L, XIRR, trailing stops, budget

```
STEPS:
  1. Fetch holdings from Kite get_holdings
  2. Fetch LTP for all held instruments
  3. Read paper_trades.json for full execution log
  4. Read portfolio_state.json for budget tracker
  5. Read Google Drive for non-Kite assets (MF NAV, FD values)
  6. Compute:
     - Total invested vs current (overall P&L %)
     - Per-instrument P&L and weight %
     - XIRR approximation
     - Week-on-week change
     - Month deployed vs ₹4L budget
     - Trailing stop levels for each position
  7. Update portfolio_state.json

OUTPUT FORMAT:
  ========= PORTFOLIO SNAPSHOT — [Date] =========
  Total Value: ₹X.XXL | Invested: ₹X.XXL | P&L: +X% | XIRR: ~X%
  Week: [+/-X%] | Month deployed: ₹X.XXL of ₹4L

  [Instrument | Qty | Avg Cost | LTP | P&L% | Weight% | Trailing Stop]

  TRAILING STOPS:
  [Any positions within 3% of their stop — flag as WARNING]

  FD CALENDAR:
  [FDs maturing in next 60 days — redirect to which bucket]
  ================================================
```

---

## SKILL-07: `annual-tax-agent`
**Trigger:** 15th March every year at 8:00 AM
**Purpose:** LTCG optimisation, tax-loss harvesting, FD maturity planning

```
STEPS:
  1. Fetch full trade history: Kite get_trades + get_order_history
  2. Read paper_trades.json for complete execution log
  3. Read Google Drive for FD maturity dates
  4. Identify:
     a. LTCG positions (held > 1 year) — estimate tax if sold
        Flag if gains > ₹1.25L exemption threshold
     b. Loss positions — tax-loss harvesting candidates
        (Sell at loss before 31 Mar, rebuy after 1 day — saves STCG tax)
     c. FDs maturing before 31 Mar — where to redirect
     d. Positions where holding 1 more month crosses 1-year LTCG threshold
  5. Compute estimated tax saving from each action

OUTPUT:
  - tax_report.json
  - Print: Prioritised action checklist before 31st March
  NOTE: Advisory only — Mahantesh decides what to act on
```

---

## Agent Definitions

### AGENT-01: `fundamental-analyst`
Spawned by SKILL-04 per sector.
Inputs: sector name, top 5 stocks by market cap.
Outputs: PE analysis, earnings trend, policy outlook, score 1–10.
Tools: Kite historical data, shell for NSE data.

### AGENT-02: `technical-analyst`
Spawned by SKILL-02 (per instrument) and SKILL-04 (per sector ETF).
Inputs: instrument token, 30–200 day OHLCV from Kite.
Outputs: DMA signals, RSI, volume trend, support/resistance, signal score 1–10.
Tools: Kite get_historical_data.

### AGENT-03: `portfolio-optimizer`
Spawned by SKILL-01 and SKILL-05.
Inputs: current allocation, target allocation, available budget.
Outputs: optimal buy list with quantities, platform, and rationale.
Tools: Kite search_instruments, get_ltp.

### AGENT-04: `macro-analyst`
Spawned by SKILL-02 and SKILL-04.
Inputs: sector list, global index proxies from Kite.
Outputs: macro tailwinds/headwinds per sector, global risk-on/off signal.
Tools: Shell (NSE, RBI data), ICICIB22 as Nasdaq proxy, GOLDBEES as risk proxy.

---

## State Files

| File | Updated by | Read by |
|---|---|---|
| `target_allocation.json` | Manual | All skills |
| `approved_instruments.json` | Manual | SKILL-02, SKILL-04 |
| `watchlist.json` | SKILL-01, SKILL-04 | SKILL-02 |
| `daily_signal.json` | SKILL-02 daily | Session start, Mahantesh |
| `sector_rotation.json` | SKILL-04 monthly | SKILL-02, SKILL-05 |
| `portfolio_state.json` | SKILL-06 + execution confirmations | All skills, session start |
| `paper_trades.json` | Execution confirmations | SKILL-06, SKILL-07 |
| `rebalancing_report.json` | SKILL-05 quarterly | Mahantesh |
| `tax_report.json` | SKILL-07 annually | Mahantesh |

---

## Responsibility Split

| Task | Mahantesh | Claude |
|---|---|---|
| Execute buy/sell orders | ✅ Daily ~5 min | — |
| Confirm executions | ✅ After each | — |
| Define target allocation | ✅ Once | — |
| Daily market analysis | — | ✅ SKILL-02 8 AM |
| Dip + exit recommendations | — | ✅ SKILL-02 daily |
| Sector scoring + rotation | — | ✅ SKILL-04 monthly |
| Portfolio health + XIRR | — | ✅ SKILL-06 weekly |
| Tax optimisation | — | ✅ SKILL-07 annually |
| Rebalancing recommendations | — | ✅ SKILL-05 quarterly |
