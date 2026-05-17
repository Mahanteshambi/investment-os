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

export interface TechnicalDetail {
  price_vs_200dma: string | null
  price_vs_50dma: string
  rsi14: number
  "52w_position_pct": number
  vol_ratio_20d_60d: number
}

export interface SectorScore {
  rank: number
  sector: string
  etf: string
  token: number
  current_price: number
  technical_score: number
  fundamental_score: number
  fii_dii_score: number
  composite_score: number
  decision: string
  monthly_allocation_inr: number
  technical_detail: TechnicalDetail
  notes: string
  consecutive_below4_months?: number
}

export interface FiiDiiData {
  date: string
  fii_net_crore: number
  dii_net_crore: number
  fii_stance: string
  dii_stance: string
  signal: string
}

export interface MacroContext {
  dxy: number
  dxy_signal: string
  us_10yr_pct: number
  brent_crude_usd: number
  oil_signal: string
  cape_ratio: number
  yield_spread_pct: number
  yield_spread_zone: string
  valuation_overlay: string
}

export interface HistoryEntry {
  month: string
  active_sector_etf: string
  scores: Record<string, number>
  below4_sectors: string[]
  rotation_from?: string
  rotation_to?: string
}

export interface ExitAlert {
  symbol: string
  alert_type: string
  status?: string
  action?: string
  consecutive_months?: number
  conviction_note?: string
  score_current?: number
}

export interface WatchCandidate {
  etf: string
  score: number
  trigger_condition: string
  note: string
}

export interface SectorRotation {
  current_month: {
    month: string
    generated_date: string
    active_sector_etf: string
    active_sector_score: number
    active_sector_allocation: string
    rotation_decision: string
    scores: SectorScore[]
    fii_dii_data: FiiDiiData
    macro_context: MacroContext
    previous_month_sector: string
    rotation_happened: boolean
    rotation_reason: string
  }
  history: HistoryEntry[]
  exit_alerts: ExitAlert[]
  watch_candidates?: WatchCandidate[]
  _last_technical_sync?: string
  _sync_errors?: string[]
}
