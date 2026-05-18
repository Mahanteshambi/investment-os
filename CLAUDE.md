# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Who I Am Working With

Mahantesh — AI Engineering Manager, based in **Malaysia (UTC+8)**. Long-term ETF investor, not a trader.
- Monthly budget: ₹4,00,000 | Time horizon: 5–10 years | Risk tolerance: up to 30% drawdown
- Indian market (IST = UTC+5:30) opens 11:45 AM Malaysia time — **always use GTT orders, never regular market/limit orders**
- Full investor profile: `user_profile.md`

---

## My Role — Brain + Kite Executor (after confirmation)

I analyse, recommend, and advise across all platforms (Kite, Coin, Vested, INDMoney, FD).

- **Kite GTT orders:** placed automatically after Mahantesh says `confirm` or `proceed` in chat
- **Non-Kite platforms** (Zerodha Coin MFs, Vested/INDMoney US stocks, FD): recommend exact amounts + steps; Mahantesh executes manually
- **Cancel:** Mahantesh says `skip` or `cancel` → no orders placed
- **Partial execution:** `confirm NIFTYBEES GOLDBEES` → place only those instruments
- A prior session's "confirm" does NOT carry over to a new session

---

## Execution Style — Sequential, Never Parallel

**CRITICAL:** Execute SKILL-02 steps one at a time. Never batch data fetches into a single parallel call.

Correct SKILL-02 order:
1. Login → confirm works
2. Fetch LTPs → report
3. Fetch OHLC → report
4. Fetch holdings → report
5. Fetch margins → report
6. Fetch GTTs → report
7. Fetch FII/DII → report
8. Fetch macro (DXY, Oil, US10yr) — one curl at a time
9. Compile and print brief
10. Wait for "confirm" before placing any orders
11. Place GTTs one at a time, report each

---

## Session Start Checklist

Every new session must:
1. Call `mcp__kite__login` — sessions expire daily
2. Read `portfolio_state.json`
3. Call `mcp__kite__get_holdings` (live, not static)
4. Call `mcp__kite__get_margins` (live, not static)
5. Read `daily_signal.json` (if exists)
6. Read `sector_rotation.json` (if exists)
7. Print 5-line context brief:
   ```
   Date: [today] | Days left in month: [X] | Budget remaining: ₹X.XXL of ₹4L
   FII/DII: [stance] | Active sector: [ETF name] (score: X/10)
   Trailing stops active: [count] positions
   Last brief: [date of last daily_signal.json]
   Pending execution confirmations: [any unconfirmed recommendations]
   ```

---

## Project Structure

```
Investing/
  CLAUDE.md                    # This file
  ARCHITECTURE.md              # Full skill step-by-step logic + agent definitions
  SKILL.md                     # Standalone skill prompts (SKILL-05 currently)
  user_profile.md              # Investor profile + goals
  trading_strategy_prompt.md   # Strategy reference

  # State files (see table below)
  approved_instruments.json    # Instrument whitelist with Kite tokens
  target_allocation.json       # Target % per bucket
  watchlist.json               # Instruments monitored daily
  sector_rotation.json         # Monthly sector scores + active sector ETF
  daily_signal.json            # Today's recommendations (gitignored)
  portfolio_state.json         # Budget tracker + trailing stops + FD calendar (gitignored)
  paper_trades.json            # Full GTT execution log (gitignored)
  user_config.json             # Account IDs, Google Sheet ID (gitignored)

  investment-os/               # Dashboard web app (separate from the AI skill system)
    backend/                   # FastAPI + DuckDB
    frontend/                  # Next.js 16 + React 19
```

---

## Investment OS Dashboard (Web App)

Full-stack portfolio dashboard — separate from the Claude skill/GTT system. Pulls data from Kite and Google Sheets to display portfolio analytics.

### Commands

```bash
# Backend (Python/FastAPI)
cd investment-os/backend
uv run uvicorn main:app --reload --port 8000

# Run a single test
uv run pytest tests/test_holdings.py -v

# Frontend (Next.js)
cd investment-os/frontend
pnpm dev          # starts on :3000
pnpm build
pnpm lint
```

### Backend Architecture

```
backend/
  main.py                 # FastAPI app, CORS, lifespan (DB init + scheduler start)
  database/
    connection.py         # DuckDB singleton connection
    schema.sql            # Schema migrations
  routers/                # Route handlers (one file per domain)
    holdings.py, portfolio.py, snapshots.py, sync.py,
    intelligence.py, sector_rotation.py, world_view.py, transactions.py
  services/               # Business logic
    kite_service.py, kite_data_fetcher.py, analytics_service.py,
    data_fetcher.py, sector_rotation_service.py, sheets_service.py,
    sync_service.py, world_data_fetcher.py, mf_intelligence.py
  models/
    schemas.py            # Pydantic v2 models
  scheduler/
    jobs.py               # APScheduler jobs (sync, snapshots)
```

**DB:** DuckDB (file: `investment_os.db`). Connection is a singleton; always use `get_db()`.
**Stack:** FastAPI + uvicorn + DuckDB + Pydantic v2 + APScheduler + kiteconnect + gspread + yfinance.

### Frontend Architecture

```
frontend/
  app/                    # Next.js App Router pages
    page.tsx              # Root / dashboard
    layout.tsx            # Root layout + providers
    providers.tsx         # TanStack Query provider
    holdings/             # Holdings page
    intelligence/         # AI intelligence page
    sector-rotation/      # Sector rotation page
    transactions/         # Transactions page
    world-view/           # Global markets page
    analysis/             # Analysis page
  components/             # Shared components
    dashboard/            # Dashboard-specific widgets
    holdings/             # Holdings table/cards
    layout/               # Shell, nav
    sector-rotation/      # Sector scorecard
    ui/                   # Base UI primitives (Base UI + Tailwind)
  lib/                    # API client, utilities
  types/                  # TypeScript types
```

**Stack:** Next.js 16 (webpack mode — use `--webpack` flag), React 19, TanStack Query v5, Tailwind CSS v4, Base UI, Recharts.
**IMPORTANT:** This Next.js version has breaking API changes. Before writing Next.js code, check `node_modules/next/dist/docs/` for current conventions.

---

## Standing Rules (Never Break)

### GTT Order Rules
- **Always GTT, never regular market/limit** — Mahantesh monitors from Malaysia
- **GTT Buy format:** trigger = 0.5% below prev close; limit = 1.5% above trigger; CNC/LIMIT/Single
- **GTT Sell (stop-loss):** trigger = stop level; limit = 1-2% below trigger
- Show full order table BEFORE placing; place one at a time; verify with `get_gtts` after

### Budget & Pacing
- Monthly ₹4L across all platforms
- `daily_target = remaining_budget / remaining_trading_days`
- Dip threshold weeks 1–3: deploy only if instrument >2% below month-open price
- Final week (days 22–30): deploy full remaining regardless of dip
- Minimum daily floor: ₹15,000

### Bucket Allocation (monthly)
| Bucket | % | ₹/month | Platform | Instruments |
|--------|---|---------|----------|-------------|
| Large Cap | 40% | ₹1,60,000 | Kite | NIFTYBEES, SETFNIF50 |
| Mid/Small | 15% | ₹60,000 | Kite | JUNIORBEES, MOM100 |
| Sector — Active | ~7.5% | ₹30,000 | Kite | Per `sector_rotation.json` |
| Sector — Secondary | ~7.5% | ₹30,000 | Kite | MODEFENCE (from Jun 2026) |
| Gold | 15% | ₹60,000 | Kite | GOLDBEES |
| International | 10% | ₹40,000 | Kite + Coin | ICICIB22 + Motilal/Mirae global MF |
| Debt/Liquid | 5% | ₹20,000 | Kite/FD | LIQUIDBEES or FD renewal |

**Active sector ETF:** read from `sector_rotation.json → current_month.active_sector_etf`. Do NOT use `target_allocation.json` for this.

**PSUBNKBEES:** STOPPED May 15 2026. No new buys. Hold existing 300 units.

### Exit Rules
- Trailing stop: 15% gain → stop at peak -8%; ratchet every 5% gain
- Sector exit: score < 4 for 2 consecutive months → stop buys, exit on stop hit
- Never sell at a loss for rebalancing
- Always state STCG/LTCG implication when recommending a sell

### Safety
- Never break FDs early
- FD maturity → park in LIQUIDBEES, STP into equity over 6 months (proceeds/6 per month)
- LTCG flag if gains exceed ₹1.25L

---

## Macro Signals (Track Every Brief)

| Signal | API | Threshold |
|--------|-----|-----------|
| DXY | `curl "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d"` | <100 bullish EM; >100 headwind |
| US 10yr yield | `curl "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval=1d&range=5d"` | Spread vs India 10yr (~7%): <2% = danger |
| Brent Crude | `curl "https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF?interval=1d&range=5d"` | >$90 = rupee pressure |
| NSE FII/DII | `mcp__shell__run_command` to `https://www.nseindia.com/api/fiidiiTradeReact` | Direct curl returns 403 (Cloudflare) |

---

## MCP Tools

| Tool | Purpose |
|------|---------|
| `mcp__kite__login` | Re-auth (do this first every session) |
| `mcp__kite__get_holdings` | Live holdings |
| `mcp__kite__get_margins` | Live cash |
| `mcp__kite__get_ltp` | Live prices |
| `mcp__kite__get_historical_data` | OHLCV (token=number, date="YYYY-MM-DD HH:MM:SS") |
| `mcp__kite__get_gtts` | Check active GTT orders |
| `mcp__kite__search_instruments` | Find instrument tokens |
| `mcp__shell__run_command` | Fetch NSE/FII data (bypasses Cloudflare) |
| `mcp__ad803142-...__read_file_content` | Read Google Drive files |
| `mcp__ad803142-...__search_files` | Search Google Drive |

**After explicit "confirm" only:**
- `mcp__kite__place_gtt_order` — place GTT
- `mcp__kite__cancel_order` — cancel stale GTTs
- `mcp__kite__modify_order` — modify GTT

**Never use:**
- `mcp__kite__place_order` — regular orders; always use GTT instead

---

## Skills Schedule

| Skill | Trigger | Output |
|-------|---------|--------|
| SKILL-01: portfolio-architect | Manual (once) | Baseline allocation + first month plan |
| SKILL-02: daily-morning-brief | Weekdays 8 AM | Buy/sell/hold recs + daily_signal.json |
| SKILL-04: sector-rotation-analyst | 1st of month 8 AM | Sector scores + sector_rotation.json |
| SKILL-05: quarterly-rebalancer | 1st Jan/Apr/Jul/Oct 8 AM | Drift report + rebalancing recs |
| SKILL-06: portfolio-dashboard | Sundays 9 AM | Weekly P&L, XIRR, trailing stops |
| SKILL-07: annual-tax-agent | 15th March 8 AM | LTCG, harvesting, FD maturity plan |

Full step-by-step logic for each skill (inputs, scoring formulas, output format) is in `ARCHITECTURE.md`.
