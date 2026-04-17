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
INPUTS:
  - NSE FII/DII API: curl "https://www.nseindia.com/api/fiidiiTradeReact"
  - Kite get_ltp: all instruments in watchlist.json
  - Kite get_historical_data: 30-day OHLCV for each instrument (token as number)
  - sector_rotation.json: active sector ETF + score
  - portfolio_state.json: remaining budget, trading days left, trailing stops, last 5 days of buys
  - Global proxies: ICICIB22 price as Nasdaq proxy, GOLDBEES as gold/risk proxy

ANALYSIS (spawn AGENT-02 for each instrument, AGENT-04 for macro):
  Per instrument:
    - dip_score: % below month-open price
    - momentum: price vs 20-DMA (above/below)
    - volume: 5-day avg vs 20-day avg (accumulation/distribution)
    - trailing_stop_check: if held position, is price below trailing stop?
    - signal: STRONG BUY / BUY / HOLD / REDUCE / EXIT

  Sector allocation rule (read from sector_rotation.json):
    - Score ≥ 7: full ₹60,000 → active sector ETF
    - Score 5–6: ₹30,000 → sector ETF + ₹30,000 → NIFTYBEES
    - Score < 5: skip sector ETF → redirect ₹60,000 → Large Cap

  Exit checks:
    - Any held position with trailing stop breached → EXIT recommendation
    - Any sector with score < 4 for 2nd consecutive month → REDUCE recommendation

  Budget pacing:
    - daily_target = remaining_budget / remaining_trading_days
    - If behind pace (deployed < expected) → flag and increase today's recommendation
    - Final 8 trading days: recommend full remaining split daily

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
SECTORS TO ANALYSE:
  Banking (BANKBEES), IT (ITBEES), Pharma (PHARMABEES),
  PSU/CPSE (CPSEETF), PSU Banking (PSUBNKBEES),
  FMCG, Auto, Infrastructure, Energy
  Global: Nasdaq (ICICIB22), Emerging Markets

PER SECTOR (spawn AGENT-01 for fundamental, AGENT-02 for technical, AGENT-04 for macro):

  FUNDAMENTAL (30% weight):
    - PE ratio vs 5-year average (overvalued/undervalued)
    - Earnings growth trend (last 2 quarters)
    - Policy tailwinds: RBI, govt spending, PLI schemes, budget allocations
    - Score: 1–10

  TECHNICAL (40% weight):
    - Fetch 200-day history via Kite get_historical_data
    - Price vs 200-DMA, 50-DMA
    - RSI-14: >60 bullish, <40 bearish
    - 52-week position: near high/mid/low
    - Volume: 20-day avg vs 60-day avg
    - Score: 1–10

  FII/DII FLOW (30% weight):
    - Net FII buying/selling in sector (from weekly FII data)
    - Consecutive days of institutional accumulation
    - Score: 1–10

  COMPOSITE SCORE = (Fundamental*0.3) + (Technical*0.4) + (FII_DII*0.3)

  DECISION:
    Score ≥ 7: BUY — full ₹60,000/month
    Score 5–6: HOLD — ₹30,000/month, balance to Large Cap
    Score < 5: AVOID — ₹0, redirect to Large Cap

EXIT CHECKS:
  - Previous month's active sector: has score dropped below 4?
    → Yes: recommend stopping new buys, set trailing stop
  - Any sector ETF position with >15% gain: set trailing stop at peak - 8%

OUTPUTS:
  - sector_rotation.json (all scores + active_sector_etf for this month)
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
