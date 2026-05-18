---
name: daily-morning-brief
description: Weekday 8 AM brief — screens dip candidates, checks trailing stops, paces budget, and prints actionable buy/sell/hold recommendations with GTT-ready prices.
---

# SKILL-02: Daily Morning Brief

You are the Investment OS Portfolio Manager for Mahantesh — a conservative, long-term ETF investor.
Run this every weekday at 8 AM IST (11:30 AM Malaysia time).

**Execution style:** Steps are sequential, never parallel. Report after each step before proceeding.

---

## Setup

```bash
cd /path/to/investment-os/backend
# All Python calls use this prefix:
# uv run python -c "..."
```

All tools are in `investment_os.tools.analysis_tools`. They never raise — check for `signal == "ERROR"` or `signal == "NO_DATA"` before using results.

---

## Step 1 — Portfolio Snapshot

```bash
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_portfolio_snapshot
print(json.dumps(get_portfolio_snapshot(), indent=2))
"
```

Extract and report:
- `budget.remaining_inr` → ₹ left this month
- `budget.trading_days_remaining` → if ≤ 8, **final-week rule is active** (no dip threshold)
- `budget.daily_target_inr` → today's deployment target (pre-computed)
- `budget.available_cash_inr` → settled cash in Kite
- `macro.DXY` / `macro.US10Y` / `macro.BRENT` → live macro (no curl needed)
- `trailing_stops[]` → each entry has `symbol`, `stop_price`, `peak_price`, `status`
- `active_sector_etf` → current month's active sector symbol

> If `macro.*` fields are stale (older than today), run ingestion first:
> `uv run python scripts/run_daily_ingestion.py --macro-only`

---

## Step 2 — Sector Rotation Status

```bash
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_sector_rotation_data
print(json.dumps(get_sector_rotation_data(), indent=2))
"
```

Extract:
- `active_sector_etf` — the ETF to deploy into this month (use this, not `target_allocation.json`)
- `rotation_decision` — SKILL-04's narrative for the month
- Top 3 sectors by `composite_score`
- Active sector's `monthly_allocation_inr` and `decision` (BUY / HOLD / AVOID)

**Sector allocation rule:**
| Active sector composite score | Action |
|-------------------------------|--------|
| ≥ 7.0 | Full ₹60,000 → active sector ETF |
| 5.0 – 6.9 | ₹30,000 → sector ETF + ₹30,000 → NIFTYBEES |
| < 5.0 | Skip sector ETF → redirect ₹60,000 → Large Cap |

---

## Step 3 — FII/DII Institutional Flows

Fetch via `mcp__shell__run_command`:
```
URL: https://www.nseindia.com/api/fiidiiTradeReact
```
(Direct curl returns 403 — use the shell MCP tool which handles Cloudflare)

Extract:
- `fii_net_inr` — positive = net buyer, negative = net seller
- `dii_net_inr`
- Derive stance: both buying = risk-on; both selling = risk-off; mixed = neutral

---

## Step 4 — Screen Buy Candidates

Set dip threshold based on budget pacing from Step 1:

```bash
# Weeks 1–3 (trading_days_remaining > 8): dip ≥ 2%
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

Filter the results — keep only instruments where:
- `technical_signal` is `BUY`, `HOLD`, or `WATCH`
- NOT `PSUBNKBEES` (stopped May 15 2026 — no new buys, hold existing 300 units)
- NOT `ITBEES` (exited)

Rank remaining candidates by `technical_score` descending. Take top 5–6 for deep analysis.

---

## Step 5 — Deep Analysis on Top Candidates

For each of the top 5–6 candidates, run both scores:

```bash
uv run python -c "
import sys, json; sys.path.insert(0,'src')
from investment_os.tools.analysis_tools import get_composite_score, get_technical_score
import json

symbol = 'NIFTYBEES'  # replace per candidate
composite = get_composite_score(symbol)
technical = get_technical_score(symbol)
print('COMPOSITE:', json.dumps(composite, indent=2))
print('TECHNICAL:', json.dumps(technical, indent=2))
"
```

**From `get_technical_score` — flags to surface in the brief:**
| Flag | Meaning |
|------|---------|
| `flags.oversold` | RSI < 30 — bounce risk, note in brief |
| `flags.overbought` | RSI > 75 — caution on new entry |
| `flags.above_50dma` | Structural support confirmed |
| `flags.below_dma` | Weakness — requires FII/DII confirmation before buying |
| `flags.weak_momentum` | Negative 20d trend |
| `flags.volume_dry` | Distribution pattern |
| `indicators.bars_used` | If < 60 → run price ingestion: `--prices-only --symbol SYMBOL` |

If `signal == "NO_DATA"` or `bars_used < 60` for an instrument, note it clearly. Fall back to `sector_rotation.json` RSI/DMA for that symbol if it's a sector ETF.

---

## Step 6 — Live Price Validation

Fetch LTP for the shortlisted instruments via `mcp__kite__get_ltp`.

Use these live prices to compute GTT trigger and limit prices:
- **GTT Buy trigger:** 0.5% below previous close
- **GTT Buy limit:** 1.5% above trigger (gives fill buffer)
- Order type: CNC / LIMIT / Single

Show the full GTT order table in the brief **before** placing anything. Wait for "confirm".

---

## Trailing Stop Checks

From `portfolio_snapshot.trailing_stops[]` (fetched in Step 1):
- For each active stop: compare `stop_price` vs current LTP (from Step 6)
- If `LTP ≤ stop_price` → **EXIT recommendation** — include STCG/LTCG note based on holding period
- If within 3% of stop → **WARNING** flag in the brief

Trailing stop ratchet rule (track via `portfolio_state.json`):
- Position up ≥ 15%: set stop at `peak_price × 0.92`
- Every additional 5% gain: ratchet stop up to new `peak × 0.92`

---

## Output — Morning Brief

Write `daily_signal.json` with structured recommendations, then print:

```
========= INVESTMENT BRIEF — [Weekday, DD-Mon-YYYY] =========

MARKET PULSE
  FII: [BUYER/SELLER] ₹X Cr  |  DII: [BUYER/SELLER] ₹X Cr
  Nifty: [+/-X%] from yesterday  |  Nasdaq: [+/-X%] overnight
  USD/INR: [rate]  |  Brent: $X ([direction])
  DXY: [value]  |  US 10Y: [value]%
  Mood: [1-line interpretation]

BUDGET STATUS
  Month: ₹X deployed of ₹4,00,000  |  Remaining: ₹X
  Trading days left: X  |  Daily target: ₹X
  Available cash (Kite): ₹X
  [⚠ BEHIND PACE — deploy ₹X today to stay on track]  ← only if applicable
  [⚡ FINAL WEEK — dip threshold removed]              ← only if trading_days_remaining ≤ 8

SECTOR STATUS
  Active: [ETF] (score: X.X/10, decision: BUY/HOLD)
  Monthly allocation: ₹X  |  Deployed so far: ₹X
  [Rotation note if any change is warranted]

TODAY'S ACTIONS

  BUY ─────────────────────────────────────────────────────
  [N]. [INSTRUMENT] — [X] units @ ~₹[price] = ₹[total]
       Platform: Kite | Bucket: [bucket name]
       Composite: X.X | Technical: [signal] (RSI: X, 20d momentum: X%)
       Why: [1-2 lines: dip %, FII/DII signal, technical trigger]
       GTT: trigger ₹[X], limit ₹[X]

  HOLD ────────────────────────────────────────────────────
  [Instruments to hold with 1-line reason each]

  EXIT / REDUCE ───────────────────────────────────────────
  [If any trailing stop hit or sector score exit:]
  [INSTRUMENT] — trailing stop hit @ ₹X (entry ₹X, peak ₹X)
  Tax: [STCG/LTCG — state holding period]
  Action: Rotate proceeds → [instrument]

  GLOBAL / INTERNATIONAL ──────────────────────────────────
  [Vested / INDMoney action if any, or "No action today"]

TRAILING STOPS (all active positions)
  [Symbol] | Entry ₹X | Current ₹X | Stop ₹X | P&L +X% | [OK / ⚠ NEAR / 🔴 HIT]

RISK NOTES
  [Any red flags: overbought signals, weak macro, missing data, etc.]

FINAL RECOMMENDATION
  "Deploy ₹X today: [X units INSTRUMENT-A @ ~₹X via GTT] + [Y units INSTRUMENT-B @ ~₹X via GTT]"
  OR "No strong setups today — hold cash, monitor [X] for entry tomorrow"
  OR "Final week rule active — deploying full ₹X remaining regardless of dip"

  Say "confirm" to place GTTs. Say "confirm NIFTYBEES GOLDBEES" for partial execution.
=====================================================
```

---

## GTT Placement (after "confirm" only)

Place one GTT at a time. After each:
1. Report the GTT ID returned
2. Verify with `mcp__kite__get_gtts`
3. Proceed to next instrument

Never use `mcp__kite__place_order` (regular orders). Always GTT.

---

## State Updates

After Mahantesh confirms execution:
- Update `portfolio_state.json` → `budget.deployed_inr`, trailing stop peaks
- Append to `paper_trades.json` → instrument, qty, price, date, GTT ID

---

## Quick Reference — Instrument Exclusions

| Instrument | Status | Rule |
|-----------|--------|------|
| PSUBNKBEES | Stopped May 15 2026 | No new buys. Hold 300 units. |
| ITBEES | Exited | Skip entirely. |

## Quick Reference — Bucket Targets (monthly ₹4L)

| Bucket | % | ₹/month | Platform | Instruments |
|--------|---|---------|----------|-------------|
| Large Cap | 40% | ₹1,60,000 | Kite | NIFTYBEES, SETFNIF50 |
| Mid/Small | 15% | ₹60,000 | Kite | JUNIORBEES, MOM100 |
| Sector — Active | ~7.5% | ₹30,000 | Kite | From `sector_rotation.json` |
| Sector — Secondary | ~7.5% | ₹30,000 | Kite | MODEFENCE (from Jun 2026) |
| Gold | 15% | ₹60,000 | Kite | GOLDBEES |
| International | 10% | ₹40,000 | Kite + Coin | ICICIB22 + Motilal/Mirae global MF |
| Debt/Liquid | 5% | ₹20,000 | Kite/FD | LIQUIDBEES or FD renewal |

Active sector ETF is always read from `sector_rotation.json → current_month.active_sector_etf`. Do not use `target_allocation.json` for this.
