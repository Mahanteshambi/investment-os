---
name: sector-rotation-analyst
description: Monthly 12-sector scoring via Kite OHLCV. Computes technical indicators, applies fundamental+FII/DII overlay, ranks all sectors, updates sector_rotation.json.
---

# Sector Rotation Analyst (SKILL-04)

You are the sector rotation analyst for Mahantesh's Investment OS.
Run this on the 1st of every month (or on demand). Fetch live OHLCV from Kite, compute all indicators in Python, apply overlays, rank 12 sectors, update sector_rotation.json.

## Step 1 — Fetch OHLCV for all 12 sectors in parallel

Call `mcp__kite__get_historical_data` for each token below. Use `interval="day"`, `from_date` = ~13 months ago (for 200-DMA headroom), `to_date` = today.

| ETF | Token | Sector |
|-----|-------|--------|
| CPSEETF | 595969 | PSU/CPSE |
| PHARMABEES | 1273089 | Pharma |
| MODEFENCE | 6385665 | Defence |
| METALIETF | 6364417 | Metal |
| ENERGY | 194503681 | Energy (short history — 200DMA may be unavailable) |
| INFRABEES | 5138433 | Infrastructure |
| AUTOBEES | 2017281 | Auto |
| PSUBNKBEES | 3848193 | PSU Banking |
| MOREALTY | 5935105 | Realty |
| BANKBEES | 2928385 | Banking |
| BFSI | 1336321 | BFSI |
| ITBEES | 4885505 | IT |

## Step 2 — Compute technical indicators via Python (Bash tool)

Write and run a Python script that takes the raw close/volume arrays and outputs a table. Use this exact scoring logic:

```python
def compute_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag*(period-1) + gains[i]) / period
        al = (al*(period-1) + losses[i]) / period
    return round(100 - 100/(1 + ag/al), 1) if al > 0 else 100.0

def tech_score(vs200, vs50, rsi, w52, volr):
    # vs200: % diff from 200DMA (None = insufficient history)
    # vs50:  % diff from 50DMA
    # w52:   52-week position % (0-100)
    # volr:  volume ratio 20d/60d
    s = 0.0
    if vs200 is None: s += 1.5          # neutral — no 200DMA data
    elif vs200 >= 5:  s += 3.0
    elif vs200 >= 2:  s += 2.5
    elif vs200 >= 0:  s += 2.0
    elif vs200 >= -2: s += 1.0
    elif vs200 >= -5: s += 0.5
    # else 0

    if   vs50 >= 2:   s += 2.0
    elif vs50 >= 0:   s += 1.5
    elif vs50 >= -2:  s += 0.5
    # else 0

    if   rsi >= 60:   s += 2.0
    elif rsi >= 50:   s += 1.5
    elif rsi >= 40:   s += 1.0
    elif rsi >= 30:   s += 0.5
    # else 0

    if   w52 >= 80:   s += 2.0
    elif w52 >= 60:   s += 1.5
    elif w52 >= 40:   s += 1.0
    elif w52 >= 25:   s += 0.5
    # else 0

    if   volr >= 1.2: s += 1.0
    elif volr >= 0.8: s += 0.5
    # else 0

    return round(s, 1)
```

For each sector: extract last close as current_price; compute 200-DMA (mean of last 200 closes, skip if <200 candles → vs200=None); compute 50-DMA; RSI-14 via Wilder's; 52w position using last 252 candles (or all available); vol ratio = mean(last 20 vols)/mean(last 60 vols).

Print a summary table: Sector | Price | 200DMA | vs200% | 50DMA | vs50% | RSI | 52wPos% | VolR | TechScore

## Step 3 — Apply fundamental and FII/DII overlays (qualitative, score 1–10)

**Fundamental overlay — key factors to assess:**
- DXY vs 100 threshold (below = bullish for India/real assets)
- Brent crude vs $90 (above = good for E&P/CPSE, bad for autos/consumption)
- CAPE ratio (>30 = elevated, prefer value sectors)
- RBI rate cycle (cut = banking positive)
- Sector-specific: PLI schemes, budget capex, earnings trend, policy tailwinds

**FII/DII overlay — use NSE data:**
- Both buying = 9–10 | One buying = 6–7 | Both selling = 2–3
- Sector preference: FII favours pharma/IT/largecap banks; DII favours domestic infra/consumption

**Composite score = technical×0.4 + fundamental×0.3 + fii_dii×0.3**

## Step 4 — Rank and decide

Sort all 12 sectors by composite score descending.

Decision thresholds:
- composite ≥ 7.0 → BUY (if #1 and above current active sector by ≥1.0 → ROTATE)
- composite 5.0–6.9 → HOLD
- composite < 5.0 → AVOID

**Rotation rule:** Rotate only if top sector beats current active by ≥1.0. Avoid churning on small gaps.

**Exit rule:** If any sector has appeared in `below4_sectors[]` for 2 consecutive months in history[] → stop new buys, place trailing stop sell GTT.

## Step 5 — Update sector_rotation.json

- Update `current_month{}` with all 12 scored sectors, new `generated_date`, `active_sector_etf`, `rotation_decision`
- Append compact entry to `history[]` (max 12 entries, drop oldest on overflow)
- Update `exit_alerts[]` for any triggered exits
- Update `watch_candidates[]` with strong non-active sectors (scores 7.5+)

## Step 6 — Print scorecard

```
========= SECTOR ROTATION — [Month Year] =========
Rank  ETF          Tech  Fund  FII   Score   Decision
 1.   CPSEETF      9.0   9.0   9.0   9.0     BUY (active) ₹60K
 2.   PHARMABEES  10.0   7.5   8.5   8.8     HOLD
...
ROTATION: [NO ROTATION / ROTATING FROM X TO Y]
EXITS: [any triggered]
===================================================
```

---

---
name: quarterly-rebalancer
description: Checks portfolio allocation drift and recommends corrections across all assets.
---

# Quarterly Rebalancer Workflow (SKILL-05)

You are the portfolio-optimizer agent.
Your goal is to check for allocation drift and recommend corrections to keep Mahantesh's portfolio aligned with the target allocation.

## Steps
1. Read `target_allocation.json` for target percentages.
2. Fetch Kite holdings via `mcp__kite__get_holdings`.
3. Read Google Drive Ambi Portfolio sheet for non-Kite assets (MF/Coin, Vested/US, FD, PPF, PF, Savings).
4. Compute the current percentage per bucket across ALL assets combined.
5. Flag any bucket that has drifted > target ± 5%.
6. For overweight buckets:
   - If gain > 0: recommend trim, state LTCG/STCG implication.
   - If at loss: never sell, just recommend stopping new buys in that bucket.
7. For underweight buckets: prioritise them in the next month's daily briefs.
8. Calculate the optimal rebalancing quantities to bring the portfolio back into alignment.

## Outputs
1. Write the analysis to `rebalancing_report.json`.
2. Print a Drift table + specific rebalancing recommendations with tax notes.

**NOTE:** Never execute any trades in this skill — Mahantesh decides and executes rebalancing recommendations manually.