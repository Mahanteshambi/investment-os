# Investment OS — Web Dashboard

Next.js + FastAPI dashboard for visualising Mahantesh's investment portfolio.  
Part of the larger Investment OS project — see `../README.md` for the full picture.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (webpack mode), React 19, Tailwind CSS v4 |
| Charts | Recharts v3 |
| Data fetching | TanStack Query v5 |
| Backend | FastAPI (Python 3.12), uvicorn |
| Database | DuckDB (local file: `backend/data/investment_os.duckdb`) |
| Package manager | `pnpm` (frontend), `uv` (backend) |

---

## Running Locally

### Backend
```bash
cd investment-os/backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

Health check:
```bash
curl http://localhost:8000/health
```

Seed sample data (first run, optional):
```bash
uv run seed-data --reset --days 60
```

### Frontend
```bash
cd investment-os/frontend
"$HOME/Library/pnpm/pnpm" install
"$HOME/Library/pnpm/pnpm" dev
# Open http://localhost:3000
```

**Use `pnpm` only** — do not use `npm` in this workspace path.

---

## Environment Variables

Create `investment-os/backend/.env` from `.env.example`:

```env
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_ACCESS_TOKEN=auto-updated after login
GOOGLE_SHEETS_CREDENTIALS_JSON=./credentials/google_service_account.json
GOOGLE_SHEET_ID=[google_sheet_id from user_config.json]
DATABASE_PATH=./data/investment_os.duckdb
SECTOR_ROTATION_JSON_PATH=../../sector_rotation.json   # optional override
```

### Kite session (once per day)
```bash
# Get login URL
curl http://localhost:8000/api/sync/kite/login-url

# After login, exchange request_token
curl -X POST http://localhost:8000/api/sync/kite/session \
  -H "Content-Type: application/json" \
  -d '{"request_token":"PASTE_TOKEN","persist":true}'
```

---

## Pages

| Route | Status | Description |
|-------|--------|-------------|
| `/` | ✅ Live | Dashboard — summary metrics, allocation breakdown, drift vs target, top movers, holdings |
| `/holdings` | ✅ Live | Full holdings table with filters (asset class, source, sort) |
| `/intelligence` | ✅ Live | MF Intelligence — Crawl4AI + Gemini watchdog for mutual fund changes |
| `/sector-rotation` | ✅ Live | 12-sector rotation analysis — scores, charts, history, exit alerts |
| `/analysis` | 🔜 Phase 2 | Agent-driven analysis (Google ADK) — disabled in sidebar |

---

## Sector Rotation Page (`/sector-rotation`)

The main new feature. Reads from `../sector_rotation.json` (source of truth maintained by Claude SKILL-04).

**Components:**

| Component | What it shows |
|-----------|---------------|
| `SectorRotationHeader` | Active sector ETF + score, rotation decision, macro strip (DXY / Oil / FII/DII / CAPE), **Sync button** |
| `SectorScoreChart` | Horizontal bar chart — all 12 sectors ranked by composite score, color-coded green/yellow/red |
| `ScoreHistoryChart` | Line chart — top 6 sectors across rolling months from `history[]` |
| `SectorScoreTable` | Ranked table with Tech / Fundamental / FII/DII / Composite score bars. Click any row to expand technical detail + notes |
| `ExitAlerts` | Active exit alerts + executed positions + watch candidates for next rotation |

**Sync button behaviour:**
- Calls `POST /api/sector-rotation/sync`
- Fetches fresh OHLCV from Kite for all 12 sector ETFs (13 months of daily data)
- Recomputes all 5 technical indicators: 200-DMA, 50-DMA, RSI-14 (Wilder's), 52-week position, volume ratio 20d/60d
- Recomputes technical scores using the exact rubric from `ARCHITECTURE.md`
- **Preserves** existing fundamental + FII/DII qualitative scores (set by Claude during SKILL-04)
- Updates `sector_rotation.json` in place
- Shows "Technical data refreshed [datetime]" label after sync
- If Kite is disconnected → 503 error shown inline

> **Note:** Fundamental and FII/DII scores are qualitative — set monthly by Claude running SKILL-04. A Google ADK agent to automate these is planned for Phase 2.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + DB status |
| GET | `/api/portfolio/summary` | Total value, P&L, XIRR, last sync |
| GET | `/api/portfolio/allocation` | By asset class + by sector breakdown |
| GET | `/api/portfolio/performance?days=90` | Daily snapshots for chart |
| GET | `/api/holdings` | All holdings (filters: asset_class, source, sort) |
| POST | `/api/sync` | Trigger data sync from Kite + Sheets |
| GET | `/api/sync/status` | Sync log per source |
| GET | `/api/sync/kite/login-url` | Generate Kite OAuth login URL |
| POST | `/api/sync/kite/session` | Exchange request_token for access_token |
| GET | `/api/sector-rotation` | Read `sector_rotation.json` and return full data |
| POST | `/api/sector-rotation/sync` | Fetch fresh Kite OHLCV + recompute technical scores |
| GET | `/api/agents/signals` | Agent signals (hardcoded stub — Phase 2) |
| GET | `/api/mf/profiles` | MF Intelligence profiles |
| GET | `/api/mf/alerts` | MF change alerts |
| POST | `/api/mf/sync` | Run MF intelligence crawl |

---

## Database Schema (DuckDB)

Tables in `backend/data/investment_os.duckdb`:

| Table | Purpose |
|-------|---------|
| `holdings` | All holdings (Kite equity/ETF + Sheets: MF, FD, PPF, PF, savings) |
| `daily_snapshots` | Daily portfolio value + allocation % (for performance chart) |
| `transactions` | Trade history |
| `agent_outputs` | Agent signal log |
| `sync_log` | Data sync audit trail |
| `mf_profiles` | MF fund metadata (ISIN, category, expense ratio, AUM) |
| `mf_factsheets` | Monthly factsheet data (returns, equity/debt/cash %) |
| `mf_sector_weights` | Per-factsheet sector weights |
| `mf_stock_holdings` | Per-factsheet top stock holdings |
| `mf_alerts` | MF change alerts (manager, objective, category, sector drift) |

Schema: `backend/database/schema.sql`

---

## Backend Services

| Service | File | Purpose |
|---------|------|---------|
| `KiteService` | `services/kite_service.py` | Kite holdings, positions, margins, historical data |
| `SheetsService` | `services/sheets_service.py` | Google Sheets portfolio data |
| `SyncService` | `services/sync_service.py` | Orchestrates Kite + Sheets sync into DB |
| `AnalyticsService` | `services/analytics_service.py` | Portfolio summary + sector exposure calculations |
| `MFIntelligence` | `services/mf_intelligence.py` | Crawl4AI + Gemini MF change detection |
| `SectorRotationService` | `services/sector_rotation_service.py` | Load/sync sector_rotation.json, OHLCV scoring |

---

## Key Technical Decisions

- **DuckDB over SQLite/Postgres** — columnar, fast for analytical queries, zero-server setup, single file
- **sector_rotation.json as source of truth** — Claude updates it via CLI; backend reads it directly (no DB migration needed for monthly Claude analysis)
- **webpack mode for Next.js** — Turbopack had path issues with this workspace path (spaces in path)
- **GTT orders always** — Mahantesh is in Malaysia (UTC+8), Indian market closes 6 PM local time, cannot monitor intraday

---

## Planned (Phase 2)

- **`/analysis` page** — Powered by Google ADK agents
- **Sector rotation agent** — `backend/agents/sector_rotation_agent.py` — auto-fetch FII/DII from NSE + macro (DXY, oil) + compute fundamental/FII/DII scores programmatically; triggered by Sync button
- **Trailing stop monitor** — Alert when any holding approaches its stop level
- **XIRR time-series** — Track XIRR week over week in `daily_snapshots`
