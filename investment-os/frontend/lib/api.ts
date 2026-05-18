import type {
  AllocationBreakdown,
  DailySnapshot,
  HoldingFilters,
  HoldingResponse,
  PortfolioSummary,
  SyncResponse,
  SyncStatus,
} from "@/types"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  return fetchJSON("/api/portfolio/summary")
}

export async function getPortfolioPerformance(days = 90): Promise<DailySnapshot[]> {
  return fetchJSON(`/api/portfolio/performance?days=${days}`)
}

export async function getPortfolioAllocation(): Promise<AllocationBreakdown> {
  return fetchJSON("/api/portfolio/allocation")
}

export async function getHoldings(filters?: HoldingFilters): Promise<HoldingResponse[]> {
  const params = new URLSearchParams()
  if (filters?.asset_class) params.set("asset_class", filters.asset_class)
  if (filters?.source) params.set("source", filters.source)
  if (filters?.sort) params.set("sort", filters.sort)
  const qs = params.toString()
  return fetchJSON(`/api/holdings${qs ? `?${qs}` : ""}`)
}

export async function triggerSync(sources: string[]): Promise<SyncResponse> {
  return fetchJSON("/api/sync", {
    method: "POST",
    body: JSON.stringify({ sources }),
  })
}

export async function getSyncStatus(): Promise<SyncStatus[]> {
  return fetchJSON("/api/sync/status")
}

// Transactions
export async function getTransactions(params?: {
  ticker?: string
  transaction_type?: string
  bucket?: string
  from_date?: string
  to_date?: string
}): Promise<import("@/types").Transaction[]> {
  const p = new URLSearchParams()
  if (params?.ticker) p.set("ticker", params.ticker)
  if (params?.transaction_type) p.set("transaction_type", params.transaction_type)
  if (params?.bucket) p.set("bucket", params.bucket)
  if (params?.from_date) p.set("from_date", params.from_date)
  if (params?.to_date) p.set("to_date", params.to_date)
  const qs = p.toString()
  return fetchJSON(`/api/transactions${qs ? `?${qs}` : ""}`)
}

export async function getTransactionSummary(): Promise<import("@/types").TransactionSummary> {
  return fetchJSON("/api/transactions/summary")
}

export async function getDeploymentSeries(): Promise<import("@/types").DeploymentPoint[]> {
  return fetchJSON("/api/transactions/deployment-series")
}

export async function getTransactionXirr(): Promise<{
  overall_xirr: number | null
  simple_return_pct: number | null
  per_bucket: Record<string, number | null>
  per_bucket_simple: Record<string, number | null>
  total_current_value: number
  total_invested: number
  days_active: number
}> {
  return fetchJSON("/api/transactions/xirr")
}

export async function getPnlBySymbol(): Promise<Array<{
  symbol: string
  bucket: string
  invested: number
  redeemed: number
  current_value: number
  total_return: number
  return_pct: number
  net_qty: number
  buy_count: number
  sell_count: number
  first_trade: string | null
  last_trade: string | null
}>> {
  return fetchJSON("/api/transactions/pnl-by-symbol")
}

export async function bulkImportTransactions(
  transactions: import("@/types").TransactionIn[]
): Promise<{ inserted: number; skipped: number; errors: string[] }> {
  return fetchJSON("/api/transactions/bulk-import", {
    method: "POST",
    body: JSON.stringify({ transactions }),
  })
}

// MF Intelligence
export async function syncMFIntelligence() {
  return fetchJSON("/api/mf/sync", { method: "POST" })
}

export async function getMFProfiles() {
  return fetchJSON("/api/mf/profiles")
}

export async function getMFAlerts() {
  return fetchJSON("/api/mf/alerts")
}

export async function getMFFactsheets(isin: string) {
  return fetchJSON(`/api/mf/factsheets/${isin}`)
}

export async function getSectorRotation(): Promise<import("@/types").SectorRotation> {
  return fetchJSON("/api/sector-rotation")
}

export async function syncSectorRotation(): Promise<{
  status: string
  synced_at: string
  sectors_updated: number
  errors: string[]
  data: import("@/types").SectorRotation
}> {
  return fetchJSON("/api/sector-rotation/sync", { method: "POST" })
}

export async function getKiteLoginUrl(): Promise<{ login_url: string }> {
  return fetchJSON("/api/sync/kite/login-url")
}

export async function submitKiteToken(requestToken: string): Promise<any> {
  return fetchJSON("/api/sync/kite/session", {
    method: "POST",
    body: JSON.stringify({ request_token: requestToken, persist: true }),
  })
}
