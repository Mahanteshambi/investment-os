# Investment OS (MVP)

Minimal two-service setup for tracking your investment portfolio:

- `backend` = FastAPI + DuckDB API
- `frontend` = Next.js dashboard (webpack mode for stability)

## Purpose

This project is optimized for long-term portfolio management:

- See total portfolio value, P&L, and allocation
- View holdings by source/type
- Track performance trend and snapshots
- Trigger data sync jobs

## Prerequisites

- Python 3.12+
- `uv` installed
- Node.js 20+
- `pnpm` available at `~/Library/pnpm/pnpm` (or on PATH)

## 1) Run Backend

```bash
cd "investment-os/backend"
uv sync
uv run uvicorn main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Seed local sample data (optional, recommended for first run):

```bash
cd "investment-os/backend"
uv run seed-data --reset --days 60
```

Load real data from Kite + Google Sheets:

1. Create `investment-os/backend/.env` from `.env.example`
2. Fill:
   - `KITE_API_KEY`
   - `KITE_API_SECRET`
   - `KITE_ACCESS_TOKEN` (optional if generated via API below)
   - `GOOGLE_SHEETS_CREDENTIALS_JSON` (service-account JSON path)
   - `GOOGLE_SHEET_ID` (already set to your portfolio sheet)
3. Generate Kite session token once per day:

```bash
curl http://localhost:8000/api/sync/kite/login-url
# open login_url, complete login, copy request_token from redirect URL

curl -X POST http://localhost:8000/api/sync/kite/session \
  -H "Content-Type: application/json" \
  -d '{"request_token":"PASTE_REQUEST_TOKEN","persist":true}'
```

4. Start backend sync:

```bash
curl -X POST http://localhost:8000/api/sync \
  -H "Content-Type: application/json" \
  -d '{"sources":["all"]}'
```

Check ingestion status:

```bash
curl http://localhost:8000/api/sync/status
```

## 2) Run Frontend

Use `pnpm` only (do not use npm in this workspace path).

```bash
cd "investment-os/frontend"
"$HOME/Library/pnpm/pnpm" install
"$HOME/Library/pnpm/pnpm" dev
```

Open `http://localhost:3000`.

## Notes

- Dev/build scripts use webpack mode to avoid Turbopack path issues.
- API base URL defaults to `http://localhost:8000`.
- To override: set `NEXT_PUBLIC_API_URL`.
- Backend now fails sync with clear errors if Kite/Google credentials are missing.
