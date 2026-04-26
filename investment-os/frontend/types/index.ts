export interface PortfolioSummary {
  total_value: number
  invested_value: number
  total_pnl: number
  total_pnl_pct: number
  day_pnl: number
  day_pnl_pct: number
  xirr: number | null
  allocation: Record<string, number>
  last_synced: string | null
}

export interface HoldingResponse {
  id: string
  asset_name: string
  ticker: string | null
  asset_class: 'equity' | 'mf' | 'etf' | 'gold' | 'cash' | 'debt'
  sub_class: string | null
  source: 'kite' | 'sheets' | 'manual'
  quantity: number | null
  avg_cost: number | null
  current_price: number | null
  current_value: number | null
  invested_value: number | null
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
  sector: string | null
  last_updated: string
}

export interface DailySnapshot {
  snapshot_date: string
  total_value: number | null
  invested_value: number | null
  total_pnl: number | null
  total_pnl_pct: number | null
  equity_pct: number | null
  mf_pct: number | null
  gold_pct: number | null
  cash_pct: number | null
  debt_pct: number | null
  nifty50_value: number | null
}

export interface AllocationBreakdown {
  by_class: Record<string, number>
  by_sector: Array<{ sector: string; value: number; pct: number }>
}

export interface AgentSignal {
  agent_name: string
  signal_type: string
  signal_value: 'bullish' | 'bearish' | 'neutral' | 'action_needed'
  summary: string
  created_at: string
}

export interface SyncResponse {
  status: string
  sources_synced: string[]
  records_updated: number
  errors: string[]
  synced_at: string
}

export interface SyncStatus {
  source: string
  status: string
  records_updated: number
  synced_at: string | null
  error_message: string | null
}

export interface HoldingFilters {
  asset_class?: string
  source?: string
  sort?: string
}
