from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class HoldingBase(BaseModel):
    asset_name: str
    ticker: Optional[str] = None
    asset_class: str  # 'equity' | 'mf' | 'etf' | 'gold' | 'cash' | 'debt'
    sub_class: Optional[str] = None
    source: str  # 'kite' | 'sheets' | 'manual'
    platform: Optional[str] = None
    quantity: Optional[float] = None
    avg_cost: Optional[float] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    invested_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    sector: Optional[str] = None


class HoldingCreate(HoldingBase):
    id: str


class HoldingResponse(HoldingBase):
    id: str
    last_updated: datetime

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    total_value: float
    invested_value: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    day_pnl_pct: float
    xirr: Optional[float] = None
    allocation: dict[str, float]
    last_synced: Optional[datetime] = None


class DailySnapshot(BaseModel):
    snapshot_date: date
    total_value: Optional[float] = None
    invested_value: Optional[float] = None
    total_pnl: Optional[float] = None
    total_pnl_pct: Optional[float] = None
    equity_pct: Optional[float] = None
    mf_pct: Optional[float] = None
    gold_pct: Optional[float] = None
    cash_pct: Optional[float] = None
    debt_pct: Optional[float] = None
    nifty50_value: Optional[float] = None


class TransactionCreate(BaseModel):
    id: str
    transaction_date: date
    asset_name: str
    ticker: Optional[str] = None
    asset_class: str
    transaction_type: str  # 'buy' | 'sell' | 'dividend' | 'sip'
    quantity: Optional[float] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    fees: float = 0.0
    source: Optional[str] = None
    notes: Optional[str] = None


class SyncRequest(BaseModel):
    sources: list[str]  # ["kite", "sheets", "all"]


class SyncResponse(BaseModel):
    status: str
    sources_synced: list[str]
    records_updated: int
    errors: list[str]
    synced_at: datetime


class SyncStatus(BaseModel):
    source: str
    status: str
    records_updated: int
    synced_at: Optional[datetime] = None
    error_message: Optional[str] = None


class KiteLoginURLResponse(BaseModel):
    login_url: str


class KiteSessionRequest(BaseModel):
    request_token: str
    persist: bool = True


class KiteSessionResponse(BaseModel):
    status: str
    message: str
    expires_at: Optional[datetime] = None


class AgentSignal(BaseModel):
    agent_name: str
    signal_type: str
    signal_value: str  # 'bullish' | 'bearish' | 'neutral' | 'action_needed'
    summary: str
    created_at: datetime


class AllocationBreakdown(BaseModel):
    by_class: dict[str, float]
    by_sector: list[dict]

class MFProfileBase(BaseModel):
    isin: str
    fund_name: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    objective: Optional[str] = None
    fund_manager: Optional[str] = None
    benchmark: Optional[str] = None
    launch_date: Optional[date] = None
    expense_ratio: Optional[float] = None
    aum_cr: Optional[float] = None

class MFProfileResponse(MFProfileBase):
    last_updated: datetime

class MFSectorWeight(BaseModel):
    id: str
    factsheet_id: str
    sector_name: str
    weight_pct: float

class MFStockHolding(BaseModel):
    id: str
    factsheet_id: str
    stock_name: str
    weight_pct: float

class MFFactsheetBase(BaseModel):
    isin: str
    factsheet_month: date
    equity_pct: Optional[float] = None
    debt_pct: Optional[float] = None
    cash_pct: Optional[float] = None
    return_1y: Optional[float] = None
    return_3y: Optional[float] = None
    return_5y: Optional[float] = None
    return_inception: Optional[float] = None
    benchmark_return_1y: Optional[float] = None
    benchmark_return_3y: Optional[float] = None
    benchmark_return_5y: Optional[float] = None
    benchmark_return_inception: Optional[float] = None
    category_return_1y: Optional[float] = None
    category_return_3y: Optional[float] = None
    category_return_5y: Optional[float] = None

class MFFactsheetResponse(MFFactsheetBase):
    id: str
    last_updated: datetime
    sector_weights: list[MFSectorWeight] = []
    stock_holdings: list[MFStockHolding] = []

class MFAlertBase(BaseModel):
    isin: str
    alert_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None

class MFAlertResponse(MFAlertBase):
    id: str
    alert_date: datetime
    is_read: bool
