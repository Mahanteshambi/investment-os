import type {
  AgentSignal,
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

export async function getAgentSignals(): Promise<AgentSignal[]> {
  return fetchJSON("/api/agents/signals")
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
