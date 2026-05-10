# Portfolio Dashboard — Build Prompt for Claude Code in Cursor

## What You Are Building

A personal investment portfolio dashboard for a long-term investor (Mahantesh, based in Malaysia).
Not a trading app. A read-only monitoring dashboard.

**Data flow:**
```
Kite Connect API ──┐
                   ├──[refresh button]──► SQLite (local) ──► Next.js Dashboard
Google Sheets API ─┘
```

Dashboard ALWAYS reads from local SQLite. Never calls external APIs at render time.
Refresh is explicit — one button, pulls latest from both sources, writes to SQLite, dashboard re-renders.

---

## Tech Stack

- **Framework:** Next.js 14 (App Router, TypeScript)
- **Styling:** Tailwind CSS + shadcn/ui components
- **Charts:** Recharts
- **Database:** SQLite via `better-sqlite3` (local file `tracker.db`)
- **Python refresh script:** `scripts/refresh.py` using `kiteconnect` + `gspread`
- **Next.js API route:** `/api/refresh` triggers the Python script
- **Package manager:** npm

---

## Directory Structure

Build exactly this structure:

```
tracker/
├── app/
│   ├── layout.tsx                  ← root layout, dark theme, sidebar nav
│   ├── page.tsx                    ← redirect to /dashboard
│   ├── dashboard/
│   │   └── page.tsx                ← overview: total value, allocation, P&L
│   ├── holdings/
│   │   └── page.tsx                ← Kite ETF + stock holdings table
│   ├── mutual-funds/
│   │   └── page.tsx                ← Coin MF holdings from Google Sheet
│   ├── other-assets/
│   │   └── page.tsx                ← FD, PPF, PF, savings, US stocks
│   ├── gtts/
│   │   └── page.tsx                ← active GTT orders from Kite
│   └── trailing-stops/
│       └── page.tsx                ← trailing stop monitoring
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx              ← shows last refreshed timestamp + Refresh button
│   │   └── RefreshButton.tsx
│   ├── dashboard/
│   │   ├── TotalValueCard.tsx
│   │   ├── AllocationPieChart.tsx
│   │   ├── BucketBreakdownTable.tsx
│   │   ├── PnLSummaryCard.tsx
│   │   └── MacroPulseCard.tsx      ← DXY, oil, yield spread (from SQLite)
│   ├── holdings/
│   │   ├── HoldingsTable.tsx
│   │   └── TrailingStopBadge.tsx
│   ├── gtts/
│   │   └── GttTable.tsx
│   └── ui/                         ← shadcn components go here
├── lib/
│   ├── db.ts                       ← SQLite connection + typed query helpers
│   ├── queries.ts                  ← all read queries (no writes from Next.js)
│   └── utils.ts                    ← formatters: ₹, %, dates
├── scripts/
│   ├── refresh.py                  ← Python: fetches Kite + GSheets → writes SQLite
│   ├── requirements.txt
│   └── init_db.py                  ← creates SQLite tables (run once)
├── types/
│   └── portfolio.ts                ← TypeScript interfaces matching DB schema
├── .env.local.example              ← document all required env vars
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## SQLite Schema

File: `tracker.db` in the project root. Create via `scripts/init_db.py`.

```sql
-- Each call to refresh creates one snapshot
CREATE TABLE IF NOT EXISTS snapshots (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  refreshed_at  TEXT NOT NULL,          -- ISO 8601, UTC
  source_kite   INTEGER DEFAULT 1,      -- 1 = Kite data included
  source_sheets INTEGER DEFAULT 1       -- 1 = Google Sheet data included
);

-- Kite ETF + stock holdings (one row per symbol per snapshot)
CREATE TABLE IF NOT EXISTS kite_holdings (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  symbol          TEXT NOT NULL,        -- e.g. NIFTYBEES
  exchange        TEXT DEFAULT 'NSE',
  quantity        INTEGER NOT NULL,
  avg_price       REAL NOT NULL,
  last_price      REAL NOT NULL,
  pnl             REAL NOT NULL,
  pnl_pct         REAL NOT NULL,
  value_inr       REAL NOT NULL,        -- quantity * last_price
  bucket          TEXT,                 -- Large Cap / Mid-Small / Gold / etc.
  t1_quantity     INTEGER DEFAULT 0,    -- unsettled (T+1)
  is_etf          INTEGER DEFAULT 1     -- 1 = ETF, 0 = stock
);

-- Active GTT orders from Kite
CREATE TABLE IF NOT EXISTS kite_gtts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  gtt_id          INTEGER NOT NULL,
  symbol          TEXT NOT NULL,
  transaction_type TEXT NOT NULL,       -- BUY or SELL
  trigger_price   REAL NOT NULL,
  limit_price     REAL NOT NULL,
  quantity        INTEGER NOT NULL,
  status          TEXT NOT NULL,        -- active / triggered / cancelled
  created_at      TEXT,
  expires_at      TEXT,
  gtt_type        TEXT                  -- buy_gtts / stop_loss
);

-- Trailing stop levels (manual config, read from portfolio_state.json)
CREATE TABLE IF NOT EXISTS trailing_stops (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  symbol          TEXT NOT NULL,
  entry_price     REAL NOT NULL,
  peak_price      REAL NOT NULL,
  stop_price      REAL NOT NULL,
  current_price   REAL NOT NULL,
  pnl_pct         REAL NOT NULL,
  buffer_pct      REAL NOT NULL,        -- (current - stop) / stop * 100
  status          TEXT NOT NULL,        -- SAFE / WATCH / TRIGGERED
  gtt_id          INTEGER               -- linked GTT sell order
);

-- Mutual funds from Zerodha Coin (Google Sheet)
CREATE TABLE IF NOT EXISTS mf_holdings (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  fund_name       TEXT NOT NULL,
  folio           TEXT,
  units           REAL NOT NULL,
  nav             REAL NOT NULL,
  value_inr       REAL NOT NULL,
  invested_inr    REAL,
  pnl_inr         REAL,
  pnl_pct         REAL,
  category        TEXT,                 -- Large Cap / Flexi Cap / ELSS etc.
  amc             TEXT,
  platform        TEXT DEFAULT 'Zerodha Coin'
);

-- Fixed deposits (Google Sheet)
CREATE TABLE IF NOT EXISTS fixed_deposits (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  bank            TEXT NOT NULL,
  principal_inr   REAL NOT NULL,
  interest_rate   REAL,                 -- % per annum
  maturity_date   TEXT,                 -- YYYY-MM-DD
  maturity_value_inr REAL,
  status          TEXT DEFAULT 'active' -- active / matured
);

-- Other assets (PPF, PF, savings, US stocks) from Google Sheet
CREATE TABLE IF NOT EXISTS other_assets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  asset_type      TEXT NOT NULL,        -- PPF / PF / Savings / US_Stock / RD
  asset_name      TEXT NOT NULL,        -- fund/bank/stock name
  value_inr       REAL NOT NULL,
  invested_inr    REAL,
  currency        TEXT DEFAULT 'INR',
  platform        TEXT,                 -- Vested / INDMoney / bank name
  notes           TEXT
);

-- Portfolio-wide aggregated summary per snapshot (pre-computed for fast dashboard)
CREATE TABLE IF NOT EXISTS portfolio_summary (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id) UNIQUE,

  -- Kite
  kite_holdings_value_inr  REAL,
  kite_cash_inr            REAL,
  kite_total_inr           REAL,
  kite_pnl_inr             REAL,
  kite_pnl_pct             REAL,

  -- Non-Kite
  mf_value_inr             REAL,
  fd_value_inr             REAL,
  ppf_value_inr            REAL,
  pf_value_inr             REAL,
  savings_inr              REAL,
  us_stocks_inr            REAL,        -- converted to INR at spot

  -- Totals
  total_portfolio_inr      REAL,
  total_invested_inr       REAL,
  total_pnl_inr            REAL,
  total_pnl_pct            REAL,

  -- Bucket allocation (actual %)
  pct_large_cap            REAL,
  pct_mid_small            REAL,
  pct_sector               REAL,
  pct_gold                 REAL,
  pct_international        REAL,
  pct_debt_liquid          REAL,
  pct_mf                   REAL,
  pct_fd                   REAL,
  pct_ppf_pf               REAL,

  -- Monthly budget
  monthly_budget_inr       REAL DEFAULT 400000,
  deployed_this_month_inr  REAL,
  remaining_this_month_inr REAL
);

-- Macro signals (from daily_signal.json or Yahoo Finance)
CREATE TABLE IF NOT EXISTS macro_signals (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
  dxy             REAL,
  dxy_signal      TEXT,
  us_10yr_pct     REAL,
  india_10yr_pct  REAL DEFAULT 7.0,
  yield_spread    REAL,
  yield_zone      TEXT,
  brent_crude_usd REAL,
  oil_signal      TEXT,
  fii_net_crore   REAL,
  dii_net_crore   REAL,
  fii_stance      TEXT,
  cape_ratio      REAL DEFAULT 33,
  evi_zone        TEXT
);

-- Indexes for fast latest-snapshot queries
CREATE INDEX IF NOT EXISTS idx_kite_holdings_snapshot ON kite_holdings(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_kite_gtts_snapshot ON kite_gtts(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_mf_holdings_snapshot ON mf_holdings(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_trailing_stops_snapshot ON trailing_stops(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_summary_snapshot ON portfolio_summary(snapshot_id);
```

---

## Python Refresh Script

File: `scripts/refresh.py`

This script:
1. Connects to Kite Connect API using env vars
2. Reads Google Sheet using service account
3. Reads `../portfolio_state.json` for trailing stops + budget data
4. Reads `../daily_signal.json` for macro signals
5. Writes everything to `../tracker.db`

```python
#!/usr/bin/env python3
"""
Portfolio refresh script.
Usage: python scripts/refresh.py
Env vars required: KITE_API_KEY, KITE_ACCESS_TOKEN, GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID
"""

import os, json, sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")

KITE_API_KEY     = os.environ["KITE_API_KEY"]
KITE_ACCESS_TOKEN = os.environ["KITE_ACCESS_TOKEN"]
SHEET_ID         = os.environ.get("GOOGLE_SHEET_ID", "[google_sheet_id from user_config.json]")
SA_JSON          = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")  # path to service account file
DB_PATH          = os.environ.get("DB_PATH", "tracker.db")
STATE_FILE       = os.environ.get("STATE_FILE", "../portfolio_state.json")
SIGNAL_FILE      = os.environ.get("SIGNAL_FILE", "../daily_signal.json")

# --- Bucket mapping for Kite symbols ---
BUCKET_MAP = {
  "NIFTYBEES":  "Large Cap",  "SETFNIF50":   "Large Cap",
  "JUNIORBEES": "Mid/Small",  "MOM100":      "Mid/Small",
  "BANKBEES":   "Sector",     "ITBEES":      "Sector",
  "PHARMABEES": "Sector",     "CPSEETF":     "Sector",
  "PSUBNKBEES": "Sector",
  "GOLDBEES":   "Gold",
  "ICICIB22":   "International",
  "LIQUIDBEES": "Debt/Liquid",
  "LIQUIDCASE": "Debt/Liquid",
}
ETF_SYMBOLS = set(BUCKET_MAP.keys())


def fetch_kite(db, snapshot_id):
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(KITE_ACCESS_TOKEN)

    # Holdings
    holdings = kite.holdings()
    for h in holdings:
        sym = h["tradingsymbol"]
        db.execute("""
            INSERT INTO kite_holdings
              (snapshot_id, symbol, exchange, quantity, avg_price, last_price,
               pnl, pnl_pct, value_inr, bucket, t1_quantity, is_etf)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snapshot_id, sym, h.get("exchange","NSE"),
            h["quantity"], h["average_price"], h["last_price"],
            h["pnl"], h["pnl"] / max(h["average_price"] * h["quantity"], 1) * 100,
            h["last_price"] * (h["quantity"] + h.get("t1_quantity",0)),
            BUCKET_MAP.get(sym, "Stock"),
            h.get("t1_quantity", 0),
            1 if sym in ETF_SYMBOLS else 0
        ))

    # Cash
    margins = kite.margins(segment="equity")
    cash = margins.get("net", 0)

    # GTTs
    gtts = kite.get_gtts()
    for g in gtts:
        trigger = g.get("condition", {})
        orders  = g.get("orders", [{}])
        order   = orders[0] if orders else {}
        db.execute("""
            INSERT INTO kite_gtts
              (snapshot_id, gtt_id, symbol, transaction_type, trigger_price,
               limit_price, quantity, status, created_at, expires_at, gtt_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snapshot_id, g["id"],
            trigger.get("tradingsymbol",""),
            order.get("transaction_type",""),
            trigger.get("trigger_values",[0])[0],
            order.get("price", 0),
            order.get("quantity", 0),
            g.get("status",""),
            g.get("created_at",""),
            g.get("expires_at",""),
            "stop_loss" if order.get("transaction_type") == "SELL" else "buy_gtts"
        ))

    return holdings, cash


def fetch_sheets(db, snapshot_id):
    """
    Read Google Sheet tabs:
      - 'Coin MF' or 'MF'   → mf_holdings
      - 'FD'                 → fixed_deposits
      - 'PPF'                → other_assets (PPF)
      - 'PF'                 → other_assets (PF)
      - 'Savings'            → other_assets (Savings)
      - 'US Stocks'          → other_assets (US_Stock)
      - '[SPOUSE]'             → other_assets ([SPOUSE])

    Expected column headers (row 1) per tab — adjust to match your actual sheet:
      Coin MF:  Fund Name | Folio | Units | NAV | Value (₹) | Invested (₹) | Category | AMC
      FD:       Bank | Principal (₹) | Interest Rate % | Maturity Date | Maturity Value (₹)
      PPF:      Description | Value (₹) | Invested (₹)
      PF:       Description | Value (₹) | Invested (₹)
      Savings:  Bank | Balance (₹)
      US Stocks: Stock | Qty | Avg Price ($) | Current Price ($) | Value ($) | Value (₹)
    """
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds  = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
    gc     = gspread.authorize(creds)
    sh     = gc.open_by_key(SHEET_ID)

    def get_tab(names):
        for name in names:
            try: return sh.worksheet(name).get_all_records()
            except: pass
        return []

    # MF
    for row in get_tab(["Coin MF", "MF", "Mutual Funds"]):
        if not row.get("Fund Name"): continue
        invested = float(str(row.get("Invested (₹)", 0) or 0).replace(",","") or 0)
        value    = float(str(row.get("Value (₹)", 0) or 0).replace(",","") or 0)
        db.execute("""
            INSERT INTO mf_holdings
              (snapshot_id, fund_name, folio, units, nav, value_inr,
               invested_inr, pnl_inr, pnl_pct, category, amc)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snapshot_id,
            row.get("Fund Name",""),
            str(row.get("Folio","")),
            float(str(row.get("Units",0) or 0).replace(",","") or 0),
            float(str(row.get("NAV",0) or 0).replace(",","") or 0),
            value, invested,
            value - invested,
            (value - invested) / max(invested,1) * 100,
            row.get("Category",""),
            row.get("AMC","")
        ))

    # FD
    for row in get_tab(["FD", "Fixed Deposits"]):
        if not row.get("Bank"): continue
        db.execute("""
            INSERT INTO fixed_deposits
              (snapshot_id, bank, principal_inr, interest_rate,
               maturity_date, maturity_value_inr)
            VALUES (?,?,?,?,?,?)
        """, (
            snapshot_id,
            row.get("Bank",""),
            float(str(row.get("Principal (₹)",0) or 0).replace(",","") or 0),
            float(str(row.get("Interest Rate %",0) or 0) or 0),
            str(row.get("Maturity Date","")),
            float(str(row.get("Maturity Value (₹)",0) or 0).replace(",","") or 0)
        ))

    # PPF, PF, Savings, US Stocks as other_assets
    for tab_names, asset_type, platform in [
        (["PPF"],           "PPF",      "PPF Account"),
        (["PF","EPF"],      "PF",       "EPFO"),
        (["Savings","Bank"],"Savings",  "Bank"),
        (["US Stocks","US"],"US_Stock", "Vested/INDMoney"),
    ]:
        for row in get_tab(tab_names):
            name  = row.get("Fund Name") or row.get("Description") or row.get("Bank") or row.get("Stock","")
            if not name: continue
            value = float(str(row.get("Value (₹)", row.get("Balance (₹)",0)) or 0).replace(",","") or 0)
            db.execute("""
                INSERT INTO other_assets
                  (snapshot_id, asset_type, asset_name, value_inr,
                   invested_inr, platform)
                VALUES (?,?,?,?,?,?)
            """, (
                snapshot_id, asset_type, name, value,
                float(str(row.get("Invested (₹)",0) or 0).replace(",","") or 0),
                platform
            ))


def compute_summary(db, snapshot_id, holdings, cash):
    """Aggregate all data into portfolio_summary."""
    def q(sql, *args):
        return db.execute(sql, args).fetchone()[0] or 0

    kite_val  = q("SELECT SUM(value_inr) FROM kite_holdings WHERE snapshot_id=?", snapshot_id)
    kite_pnl  = q("SELECT SUM(pnl) FROM kite_holdings WHERE snapshot_id=?", snapshot_id)
    kite_cost = kite_val - kite_pnl
    mf_val    = q("SELECT SUM(value_inr) FROM mf_holdings WHERE snapshot_id=?", snapshot_id)
    fd_val    = q("SELECT SUM(principal_inr) FROM fixed_deposits WHERE snapshot_id=? AND status='active'", snapshot_id)
    ppf_val   = q("SELECT SUM(value_inr) FROM other_assets WHERE snapshot_id=? AND asset_type='PPF'", snapshot_id)
    pf_val    = q("SELECT SUM(value_inr) FROM other_assets WHERE snapshot_id=? AND asset_type='PF'", snapshot_id)
    sav_val   = q("SELECT SUM(value_inr) FROM other_assets WHERE snapshot_id=? AND asset_type='Savings'", snapshot_id)
    us_val    = q("SELECT SUM(value_inr) FROM other_assets WHERE snapshot_id=? AND asset_type='US_Stock'", snapshot_id)

    total = kite_val + cash + mf_val + fd_val + ppf_val + pf_val + sav_val + us_val

    def bucket_val(bucket):
        return q("SELECT SUM(value_inr) FROM kite_holdings WHERE snapshot_id=? AND bucket=?", snapshot_id, bucket)

    db.execute("""
        INSERT OR REPLACE INTO portfolio_summary (
          snapshot_id,
          kite_holdings_value_inr, kite_cash_inr, kite_total_inr, kite_pnl_inr, kite_pnl_pct,
          mf_value_inr, fd_value_inr, ppf_value_inr, pf_value_inr, savings_inr, us_stocks_inr,
          total_portfolio_inr, total_invested_inr, total_pnl_inr, total_pnl_pct,
          pct_large_cap, pct_mid_small, pct_sector, pct_gold, pct_international, pct_debt_liquid,
          pct_mf, pct_fd, pct_ppf_pf
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        snapshot_id,
        kite_val, cash, kite_val+cash, kite_pnl, kite_pnl/max(kite_cost,1)*100,
        mf_val, fd_val, ppf_val, pf_val, sav_val, us_val,
        total, total-kite_pnl, kite_pnl, kite_pnl/max(total-kite_pnl,1)*100,
        bucket_val("Large Cap")/max(total,1)*100,
        bucket_val("Mid/Small")/max(total,1)*100,
        bucket_val("Sector")/max(total,1)*100,
        bucket_val("Gold")/max(total,1)*100,
        bucket_val("International")/max(total,1)*100,
        bucket_val("Debt/Liquid")/max(total,1)*100,
        mf_val/max(total,1)*100,
        fd_val/max(total,1)*100,
        (ppf_val+pf_val)/max(total,1)*100,
    ))


def load_trailing_stops(db, snapshot_id):
    """Read trailing stops from portfolio_state.json."""
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        for pos in state.get("trailing_stops",{}).get("positions",[]):
            current = pos.get("current_ltp", pos.get("stop",0))
            stop    = pos.get("stop",0)
            buf     = (current - stop) / max(stop,1) * 100
            status  = "TRIGGERED" if current <= stop else ("WATCH" if buf < 5 else "SAFE")
            db.execute("""
                INSERT INTO trailing_stops
                  (snapshot_id, symbol, entry_price, peak_price, stop_price,
                   current_price, pnl_pct, buffer_pct, status, gtt_id)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                snapshot_id,
                pos.get("symbol"), pos.get("entry"), pos.get("peak"),
                stop, current,
                pos.get("pnl_pct",0), buf, status,
                pos.get("gtt_id")
            ))
    except Exception as e:
        print(f"  [WARN] trailing stops: {e}")


def load_macro_signals(db, snapshot_id):
    """Read macro signals from daily_signal.json."""
    try:
        with open(SIGNAL_FILE) as f:
            sig = json.load(f)
        macro = sig.get("current",{}).get("macro", sig.get("macro",{}))
        current = sig.get("current", sig)
        db.execute("""
            INSERT INTO macro_signals
              (snapshot_id, dxy, dxy_signal, us_10yr_pct, india_10yr_pct,
               yield_spread, yield_zone, brent_crude_usd, oil_signal,
               fii_net_crore, dii_net_crore, fii_stance, cape_ratio, evi_zone)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            snapshot_id,
            macro.get("dxy"), macro.get("dxy_signal"),
            macro.get("us_10yr_pct"), macro.get("india_10yr_yield_pct", 7.0),
            macro.get("yield_spread_pct"), macro.get("yield_spread_zone"),
            macro.get("brent_crude_usd"), macro.get("oil_signal"),
            current.get("fii_net_crore"), current.get("dii_net_crore"),
            current.get("fii_stance"),
            macro.get("cape_ratio", 33), macro.get("evi_zone")
        ))
    except Exception as e:
        print(f"  [WARN] macro signals: {e}")


def main():
    print(f"[refresh] starting at {datetime.now(timezone.utc).isoformat()}")
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")

    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("INSERT INTO snapshots (refreshed_at) VALUES (?)", (now,))
    snapshot_id = cursor.lastrowid
    print(f"[refresh] snapshot_id={snapshot_id}")

    try:
        print("[refresh] fetching Kite...")
        holdings, cash = fetch_kite(db, snapshot_id)
    except Exception as e:
        print(f"[ERROR] Kite fetch failed: {e}")
        print("  → Check KITE_API_KEY and KITE_ACCESS_TOKEN in .env.local")
        holdings, cash = [], 0

    try:
        print("[refresh] fetching Google Sheet...")
        fetch_sheets(db, snapshot_id)
    except Exception as e:
        print(f"[ERROR] Sheets fetch failed: {e}")
        print("  → Check GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID in .env.local")

    load_trailing_stops(db, snapshot_id)
    load_macro_signals(db, snapshot_id)
    compute_summary(db, snapshot_id, holdings, cash)

    db.commit()
    db.close()
    print(f"[refresh] done. snapshot_id={snapshot_id}")


if __name__ == "__main__":
    main()
```

File: `scripts/requirements.txt`
```
kiteconnect>=4.0.0
gspread>=6.0.0
google-auth>=2.0.0
python-dotenv>=1.0.0
```

File: `scripts/init_db.py` — copy-paste the SQL schema above and execute with `sqlite3.connect("tracker.db")`.

---

## Next.js API Route — Refresh Endpoint

File: `app/api/refresh/route.ts`

```typescript
import { NextResponse } from "next/server";
import { exec } from "child_process";
import path from "path";

export async function POST() {
  return new Promise((resolve) => {
    const scriptPath = path.join(process.cwd(), "scripts", "refresh.py");
    const cmd = `python3 "${scriptPath}"`;

    exec(cmd, { cwd: process.cwd(), timeout: 60000 }, (err, stdout, stderr) => {
      if (err) {
        console.error("[refresh]", stderr);
        resolve(NextResponse.json({ ok: false, error: stderr }, { status: 500 }));
      } else {
        console.log("[refresh]", stdout);
        resolve(NextResponse.json({ ok: true, output: stdout }));
      }
    });
  });
}
```

---

## TypeScript Types

File: `types/portfolio.ts`

```typescript
export interface Snapshot {
  id: number;
  refreshed_at: string;
}

export interface KiteHolding {
  id: number;
  snapshot_id: number;
  symbol: string;
  exchange: string;
  quantity: number;
  avg_price: number;
  last_price: number;
  pnl: number;
  pnl_pct: number;
  value_inr: number;
  bucket: string;
  t1_quantity: number;
  is_etf: number;
}

export interface KiteGtt {
  gtt_id: number;
  symbol: string;
  transaction_type: "BUY" | "SELL";
  trigger_price: number;
  limit_price: number;
  quantity: number;
  status: string;
  expires_at: string;
  gtt_type: string;
}

export interface TrailingStop {
  symbol: string;
  entry_price: number;
  peak_price: number;
  stop_price: number;
  current_price: number;
  pnl_pct: number;
  buffer_pct: number;
  status: "SAFE" | "WATCH" | "TRIGGERED";
  gtt_id: number | null;
}

export interface MfHolding {
  fund_name: string;
  folio: string;
  units: number;
  nav: number;
  value_inr: number;
  invested_inr: number;
  pnl_inr: number;
  pnl_pct: number;
  category: string;
  amc: string;
}

export interface FixedDeposit {
  bank: string;
  principal_inr: number;
  interest_rate: number;
  maturity_date: string;
  maturity_value_inr: number;
  status: string;
}

export interface OtherAsset {
  asset_type: string;
  asset_name: string;
  value_inr: number;
  invested_inr: number;
  platform: string;
}

export interface PortfolioSummary {
  snapshot_id: number;
  kite_holdings_value_inr: number;
  kite_cash_inr: number;
  kite_total_inr: number;
  kite_pnl_inr: number;
  kite_pnl_pct: number;
  mf_value_inr: number;
  fd_value_inr: number;
  ppf_value_inr: number;
  pf_value_inr: number;
  savings_inr: number;
  us_stocks_inr: number;
  total_portfolio_inr: number;
  total_invested_inr: number;
  total_pnl_inr: number;
  total_pnl_pct: number;
  pct_large_cap: number;
  pct_mid_small: number;
  pct_sector: number;
  pct_gold: number;
  pct_international: number;
  pct_debt_liquid: number;
  pct_mf: number;
  pct_fd: number;
  pct_ppf_pf: number;
  monthly_budget_inr: number;
  deployed_this_month_inr: number;
  remaining_this_month_inr: number;
}

export interface MacroSignals {
  dxy: number | null;
  dxy_signal: string | null;
  us_10yr_pct: number | null;
  india_10yr_pct: number;
  yield_spread: number | null;
  yield_zone: string | null;
  brent_crude_usd: number | null;
  oil_signal: string | null;
  fii_net_crore: number | null;
  dii_net_crore: number | null;
  fii_stance: string | null;
  cape_ratio: number;
  evi_zone: string | null;
}

// Allocation targets for gauge/comparison
export const TARGET_ALLOCATION = {
  large_cap:     40,
  mid_small:     15,
  sector:        15,
  gold:          15,
  international: 10,
  debt_liquid:    5,
} as const;
```

---

## SQLite Query Helpers

File: `lib/db.ts`

```typescript
import Database from "better-sqlite3";
import path from "path";

const DB_PATH = path.join(process.cwd(), "tracker.db");

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: true });
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

export function getLatestSnapshotId(): number | null {
  const row = getDb()
    .prepare("SELECT id FROM snapshots ORDER BY id DESC LIMIT 1")
    .get() as { id: number } | undefined;
  return row?.id ?? null;
}

export function getLastRefreshed(): string | null {
  const row = getDb()
    .prepare("SELECT refreshed_at FROM snapshots ORDER BY id DESC LIMIT 1")
    .get() as { refreshed_at: string } | undefined;
  return row?.refreshed_at ?? null;
}
```

File: `lib/queries.ts`

```typescript
import { getDb, getLatestSnapshotId } from "./db";
import type {
  KiteHolding, KiteGtt, TrailingStop, MfHolding,
  FixedDeposit, OtherAsset, PortfolioSummary, MacroSignals
} from "@/types/portfolio";

export function getPortfolioSummary(): PortfolioSummary | null {
  const sid = getLatestSnapshotId();
  if (!sid) return null;
  return getDb()
    .prepare("SELECT * FROM portfolio_summary WHERE snapshot_id = ?")
    .get(sid) as PortfolioSummary | null;
}

export function getKiteHoldings(): KiteHolding[] {
  const sid = getLatestSnapshotId();
  if (!sid) return [];
  return getDb()
    .prepare("SELECT * FROM kite_holdings WHERE snapshot_id = ? ORDER BY value_inr DESC")
    .all(sid) as KiteHolding[];
}

export function getActiveGtts(): KiteGtt[] {
  const sid = getLatestSnapshotId();
  if (!sid) return [];
  return getDb()
    .prepare("SELECT * FROM kite_gtts WHERE snapshot_id = ? ORDER BY gtt_type, symbol")
    .all(sid) as KiteGtt[];
}

export function getTrailingStops(): TrailingStop[] {
  const sid = getLatestSnapshotId();
  if (!sid) return [];
  return getDb()
    .prepare("SELECT * FROM trailing_stops WHERE snapshot_id = ? ORDER BY buffer_pct ASC")
    .all(sid) as TrailingStop[];
}

export function getMfHoldings(): MfHolding[] {
  const sid = getLatestSnapshotId();
  if (!sid) return [];
  return getDb()
    .prepare("SELECT * FROM mf_holdings WHERE snapshot_id = ? ORDER BY value_inr DESC")
    .all(sid) as MfHolding[];
}

export function getFixedDeposits(): FixedDeposit[] {
  const sid = getLatestSnapshotId();
  if (!sid) return [];
  return getDb()
    .prepare("SELECT * FROM fixed_deposits WHERE snapshot_id = ? ORDER BY maturity_date")
    .all(sid) as FixedDeposit[];
}

export function getOtherAssets(): OtherAsset[] {
  const sid = getLatestSnapshotId();
  if (!sid) return [];
  return getDb()
    .prepare("SELECT * FROM other_assets WHERE snapshot_id = ? ORDER BY asset_type, value_inr DESC")
    .all(sid) as OtherAsset[];
}

export function getMacroSignals(): MacroSignals | null {
  const sid = getLatestSnapshotId();
  if (!sid) return null;
  return getDb()
    .prepare("SELECT * FROM macro_signals WHERE snapshot_id = ?")
    .get(sid) as MacroSignals | null;
}
```

---

## Environment Variables

File: `.env.local.example`

```bash
# Kite Connect — get API key from kite.zerodha.com/api
# Access token refreshes daily after login
KITE_API_KEY=your_api_key_here
KITE_ACCESS_TOKEN=your_daily_access_token_here

# Google Sheets — path to service account JSON file
# Create at console.cloud.google.com → IAM → Service Accounts → Keys
# Share the Google Sheet with the service account email
GOOGLE_SERVICE_ACCOUNT_JSON=/absolute/path/to/service-account.json
GOOGLE_SHEET_ID=[google_sheet_id from user_config.json]

# Paths (optional — defaults shown)
DB_PATH=tracker.db
STATE_FILE=../portfolio_state.json
SIGNAL_FILE=../daily_signal.json
```

---

## Dashboard Pages — What Each Should Show

### `/dashboard` — Overview
- **4 top cards:** Total Portfolio Value (₹) | Kite Holdings Value | Total P&L ₹ + % | Monthly Budget Remaining
- **Allocation Pie Chart:** actual % vs target % for each bucket (use two concentric rings — outer=actual, inner=target). Buckets: Large Cap (40%), Mid/Small (15%), Sector (15%), Gold (15%), International (10%), Debt/Liquid (5%), MF, FD, PPF/PF
- **Macro Pulse Card:** DXY | Oil price | Yield spread | FII stance — with colour-coded signals (green/amber/red)
- **Trailing Stop Alert:** if any stop has buffer < 5%, show alert banner at top

### `/holdings` — Kite Holdings
- Table columns: Symbol | Bucket | Qty (settled + T+1) | Avg Price | LTP | Value ₹ | P&L ₹ | P&L % | Trailing Stop
- Group by: ETFs first, then Individual Stocks
- Row colour: green if P&L > 0, red if < 0
- Trailing stop badge: shows stop price and buffer %, amber if < 5%, red if < 2%

### `/mutual-funds` — Coin MF
- Table: Fund Name | AMC | Category | Units | NAV | Value ₹ | Invested ₹ | P&L ₹ | P&L %
- Summary card: Total MF value | Total P&L

### `/other-assets` — FD + PPF + PF + US Stocks + Savings
- Grouped sections per asset type
- FD section: shows days to maturity, maturity value, STP reminder if < 60 days to maturity
- All values in ₹

### `/gtts` — Active GTT Orders
- Two sections: BUY GTTs | SELL (Stop-Loss) GTTs
- Columns: Symbol | Type | Trigger ₹ | Limit ₹ | Qty | Est. Value ₹ | Status | Expires

### `/trailing-stops` — Stop Monitoring
- Table: Symbol | Entry ₹ | Peak ₹ | Stop ₹ | Current ₹ | P&L % | Buffer % | Status
- Sort by buffer % ascending (most at risk at top)
- Status badge: SAFE (green) / WATCH <5% buffer (amber) / TRIGGERED (red)
- Linked GTT ID shown

---

## Refresh Button Behaviour

`components/layout/RefreshButton.tsx`:
- Shows last refresh time: "Last updated: 2 hours ago"
- Click → POST `/api/refresh` → loading spinner → success toast "Portfolio updated" or error toast
- On success: `router.refresh()` to re-render all Server Components with fresh SQLite data
- Disable button during refresh, timeout after 60s

---

## Visual Design

- Dark theme (slate-900 background)
- Indian Rupee symbol: ₹ (use `Intl.NumberFormat("en-IN")` for formatting)
- P&L positive: green-400 | negative: red-400
- Signal colours: SAFE/BULLISH = green | WATCH/CAUTIOUS = amber | DANGER/TRIGGERED = red
- Font: Inter (next/font)
- Sidebar: fixed left, 240px, shows nav links with icons
- Top header: shows page title + last refreshed + Refresh button

---

## Setup Instructions (include in README)

```bash
# 1. Install dependencies
npm install
pip install -r scripts/requirements.txt

# 2. Copy env file and fill in values
cp .env.local.example .env.local

# 3. Init database
python3 scripts/init_db.py

# 4. First refresh (test data pipeline)
python3 scripts/refresh.py

# 5. Start dashboard
npm run dev
# Open http://localhost:3000
```

**Kite Access Token setup:**
The access token expires daily. Two options:
1. Manual: after daily login on Kite app, paste new access token into `.env.local`
2. Automated: add a `/api/kite-login` route that handles OAuth redirect — Kite docs at kite.zerodha.com/connect/docs

**Google Sheets service account setup:**
1. Google Cloud Console → New Project → Enable Sheets API
2. IAM → Service Accounts → Create → Download JSON key
3. Share your Google Sheet with the service account email (Viewer access)
4. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to path of JSON file

---

## package.json Dependencies

```json
{
  "dependencies": {
    "next": "14.2.0",
    "react": "^18",
    "react-dom": "^18",
    "better-sqlite3": "^9.4.3",
    "recharts": "^2.12.0",
    "lucide-react": "^0.363.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "date-fns": "^3.6.0"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "@types/better-sqlite3": "^7.6.8",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "eslint": "^8",
    "eslint-config-next": "14.2.0"
  }
}
```

Also run: `npx shadcn-ui@latest init` and add components: `button card badge table alert`

---

## Important Notes for Implementation

1. **All DB reads are Server Components** — call query helpers directly in page.tsx, no useEffect needed
2. **Refresh route is the only write path** — all other API routes are read-only
3. **`better-sqlite3` is synchronous** — no async/await needed for DB queries
4. **FD maturity alert:** if maturity_date < 60 days away, show banner: "FD at [bank] matures [date] — STP into equity over 6 months"
5. **T+1 holdings:** show T+1 quantity separately in holdings table (unsettled buys)
6. **Currency formatting:** always use `new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value)`
