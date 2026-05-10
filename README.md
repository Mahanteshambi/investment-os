# Investment OS — [OWNER]

Personal investment automation system. Two layers working together:

1. **Claude analysis layer** — Claude Code runs skills (SKILL-01 through SKILL-07) that analyse markets, score sectors, generate daily briefs, and place GTT orders on Zerodha Kite via MCP.
2. **investment-os web app** — Next.js + FastAPI dashboard that visualises portfolio, holdings, MF intelligence, and sector rotation data.

**Owner:** [OWNER] · AI Engineering Manager · Malaysia (UTC+8)  
**Monthly budget:** ₹4,00,000 · **Horizon:** 5–10 years · **Goal:** Retirement + [CHILD]'s education

---

## Quick Start

### Web Dashboard
```bash
# Backend (FastAPI + DuckDB)
cd investment-os/backend
uv sync
uv run uvicorn main:app --reload --port 8000

# Frontend (Next.js)
cd investment-os/frontend
"$HOME/Library/pnpm/pnpm" install
"$HOME/Library/pnpm/pnpm" dev
# Open http://localhost:3000
```

### Claude Skills (run in Claude Code CLI)
Skills are invoked from conversation — no separate process needed.  
Say "run SKILL-02" or "run sector rotation" and Claude executes the skill using Kite MCP.

---

## Project Structure

```
Investing/
├── README.md                   ← you are here
├── CLAUDE.md                   ← Claude's operating instructions (never edit casually)
├── ARCHITECTURE.md             ← Full skill logic, data flow, scoring formulas
├── SKILL.md                    ← Standalone skill execution prompts (SKILL-04, SKILL-05)
│
├── sector_rotation.json        ← 12-sector scores, active ETF, history (updated by SKILL-04 + Sync button)
├── daily_signal.json           ← Today's buy/sell/hold recommendations (updated by SKILL-02)
├── portfolio_state.json        ← Budget tracker, trailing stops, FD calendar
├── paper_trades.json           ← Full execution log (every GTT order placed)
├── watchlist.json              ← Instruments monitored, with Kite tokens
├── approved_instruments.json   ← Whitelist of instruments Claude can recommend
├── target_allocation.json      ← Target % per bucket (Large Cap 40%, Gold 15%, etc.)
│
├── user_profile.md             ← Investor profile, goals, risk tolerance
├── project_investment_os.md    ← Project goals and phase status
│
└── investment-os/              ← Web dashboard app (see investment-os/README.md)
```

---

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| **SKILL-01** `portfolio-architect` | Manual, run once | Baseline allocation, first-month plan |
| **SKILL-02** `daily-morning-brief` | Weekdays 8 AM | Buy/sell/hold recs, dip detection, GTT order table |
| **SKILL-04** `sector-rotation-analyst` | 1st of month | Score all 12 sectors, pick active sector ETF, exit checks |
| **SKILL-05** `quarterly-rebalancer` | 1st Jan/Apr/Jul/Oct | Drift report, rebalancing recommendations |
| **SKILL-06** `portfolio-dashboard` | Sundays 9 AM | Weekly P&L, XIRR, trailing stops, budget |
| **SKILL-07** `annual-tax-agent` | 15th March | LTCG optimisation, tax-loss harvesting |

Full step-by-step logic for each skill: **ARCHITECTURE.md**  
Standalone prompts (can be copy-pasted): **SKILL.md**

---

## Sector Rotation System

Claude runs a 12-sector rotation analysis monthly (SKILL-04) using live Kite OHLCV data.

**12-sector universe (as of May 2026):**
CPSEETF · PHARMABEES · MODEFENCE · METALIETF · ENERGY · INFRABEES · AUTOBEES · PSUBNKBEES · MOREALTY · BANKBEES · BFSI · ITBEES

**Scoring formula:** `Composite = Technical×0.4 + Fundamental×0.3 + FII/DII×0.3`

**Technical score (max 10)** — computed automatically from OHLCV:
- Price vs 200-DMA (max 3), Price vs 50-DMA (max 2), RSI-14 Wilder's (max 2), 52-week position (max 2), Volume ratio 20d/60d (max 1)

**Fundamental + FII/DII scores (max 10 each)** — qualitative, set by Claude during SKILL-04 analysis based on macro context (DXY, oil, CAPE, sector policy tailwinds).

**Active sector** → always read from `sector_rotation.json` → `current_month.active_sector_etf`

**Rotation rule:** Rotate only if top sector beats current active by ≥1.0 composite score.

**Exit rule:** 2 consecutive months below score 4 → stop new buys + trailing stop GTT exit.

---

## Order Execution Flow

1. Claude runs analysis → prints GTT order table with trigger price + limit price
2. Mahantesh reviews in chat → says **"confirm"**
3. Claude calls `mcp__kite__place_gtt_order` for each instrument
4. Claude updates `paper_trades.json` + `portfolio_state.json`
5. Mahantesh confirms manual executions (Coin MF, Vested, FD) in the next message

**GTT buy format:** Trigger = prev_close × 0.995 · Limit = trigger × 1.015 · CNC delivery  
**GTT sell format:** Trigger = stop level · Limit = trigger × 0.98

**Malaysia timezone note:** Mahantesh cannot monitor intraday. Always GTT, never market/limit orders.

---

## Asset Allocation Targets

| Bucket | Target | Monthly ₹ | Platform |
|--------|--------|-----------|----------|
| Large Cap | 40% | ₹1,60,000 | Kite (NIFTYBEES, SETFNIF50) |
| Mid/Small | 15% | ₹60,000 | Kite (JUNIORBEES, MOM100) |
| Sector (rotation) | 15% | ₹60,000 | Kite (active sector ETF from sector_rotation.json) |
| Gold | 15% | ₹60,000 | Kite (GOLDBEES) |
| International | 10% | ₹40,000 | Kite (ICICIB22) + Coin (Motilal/Mirae global MF) |
| Debt/Liquid | 5% | ₹20,000 | Kite (LIQUIDBEES) or FD renewal |

---

## MCP Tools (Claude Code)

| Tool | Purpose |
|------|---------|
| `mcp__kite__get_holdings` | Live Kite holdings |
| `mcp__kite__get_margins` | Available cash |
| `mcp__kite__get_historical_data` | OHLCV for technical analysis |
| `mcp__kite__place_gtt_order` | Place GTT buy/sell (after confirm) |
| `mcp__kite__get_gtts` | Verify active GTTs |
| `mcp__claude_ai_Google_Drive__read_file_content` | Read Ambi Portfolio Google Sheet |

Google Sheet ID: `[google_sheet_id from user_config.json]`  
Contains: FD, MF/Coin, Kite stocks, PPF, PF, Savings, US Stocks (Vested), [SPOUSE]'s holdings.

---

## Current Status (May 2026)

- **Active sector:** CPSEETF (score 9.0) — rotated from PSUBNKBEES on May 5
- **ITBEES:** Exited — 1500 units sold May 7 (3 consecutive months sub-4)
- **PSUBNKBEES:** HOLD ₹30K/month (low personal conviction — conservative GTT triggers only)
- **MODEFENCE:** Strong watch candidate (#3, score 8.6) — next rotation if CPSEETF drops below 8.0
- **Dashboard:** Running at `http://localhost:3000` with Sector Rotation page live
