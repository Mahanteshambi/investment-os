CREATE TABLE IF NOT EXISTS holdings (
    id VARCHAR PRIMARY KEY,
    asset_name VARCHAR NOT NULL,
    ticker VARCHAR,
    asset_class VARCHAR NOT NULL,
    sub_class VARCHAR,
    source VARCHAR NOT NULL,
    platform VARCHAR,
    quantity DECIMAL(18,4),
    avg_cost DECIMAL(18,4),
    current_price DECIMAL(18,4),
    current_value DECIMAL(18,4),
    invested_value DECIMAL(18,4),
    unrealized_pnl DECIMAL(18,4),
    unrealized_pnl_pct DECIMAL(8,4),
    sector VARCHAR,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_date DATE NOT NULL,
    total_value DECIMAL(18,4),
    invested_value DECIMAL(18,4),
    total_pnl DECIMAL(18,4),
    total_pnl_pct DECIMAL(8,4),
    equity_pct DECIMAL(8,4),
    mf_pct DECIMAL(8,4),
    gold_pct DECIMAL(8,4),
    cash_pct DECIMAL(8,4),
    debt_pct DECIMAL(8,4),
    nifty50_value DECIMAL(18,4),
    PRIMARY KEY (snapshot_date)
);

CREATE TABLE IF NOT EXISTS transactions (
    id VARCHAR PRIMARY KEY,
    transaction_date DATE NOT NULL,
    asset_name VARCHAR NOT NULL,
    ticker VARCHAR,
    asset_class VARCHAR NOT NULL,
    transaction_type VARCHAR NOT NULL,
    quantity DECIMAL(18,4),
    price DECIMAL(18,4),
    amount DECIMAL(18,4),
    fees DECIMAL(18,4) DEFAULT 0,
    source VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS agent_outputs (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_name VARCHAR NOT NULL,
    signal_type VARCHAR,
    signal_value VARCHAR,
    summary VARCHAR,
    full_reasoning TEXT,
    metadata JSON
);

CREATE TABLE IF NOT EXISTS sync_log (
    id VARCHAR PRIMARY KEY,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    records_updated INTEGER DEFAULT 0,
    error_message VARCHAR
);

-- Mutual Fund Intelligence Tables

CREATE TABLE IF NOT EXISTS mf_profiles (
    isin VARCHAR PRIMARY KEY,
    fund_name VARCHAR NOT NULL,
    category VARCHAR,
    sub_category VARCHAR,
    objective TEXT,
    fund_manager VARCHAR,
    benchmark VARCHAR,
    launch_date DATE,
    expense_ratio DECIMAL(5,2),
    aum_cr DECIMAL(12,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mf_factsheets (
    id VARCHAR PRIMARY KEY,
    isin VARCHAR NOT NULL,
    factsheet_month DATE NOT NULL, -- Stored as 1st of the month (e.g., '2023-10-01')
    equity_pct DECIMAL(5,2),
    debt_pct DECIMAL(5,2),
    cash_pct DECIMAL(5,2),
    return_1y DECIMAL(8,4),
    return_3y DECIMAL(8,4),
    return_5y DECIMAL(8,4),
    return_inception DECIMAL(8,4),
    benchmark_return_1y DECIMAL(8,4),
    benchmark_return_3y DECIMAL(8,4),
    benchmark_return_5y DECIMAL(8,4),
    benchmark_return_inception DECIMAL(8,4),
    category_return_1y DECIMAL(8,4),
    category_return_3y DECIMAL(8,4),
    category_return_5y DECIMAL(8,4),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(isin, factsheet_month)
);

CREATE TABLE IF NOT EXISTS mf_sector_weights (
    id VARCHAR PRIMARY KEY,
    factsheet_id VARCHAR NOT NULL,
    sector_name VARCHAR NOT NULL,
    weight_pct DECIMAL(5,2) NOT NULL,
    UNIQUE(factsheet_id, sector_name)
);

CREATE TABLE IF NOT EXISTS mf_stock_holdings (
    id VARCHAR PRIMARY KEY,
    factsheet_id VARCHAR NOT NULL,
    stock_name VARCHAR NOT NULL,
    weight_pct DECIMAL(5,2) NOT NULL,
    UNIQUE(factsheet_id, stock_name)
);

CREATE TABLE IF NOT EXISTS mf_alerts (
    id VARCHAR PRIMARY KEY,
    isin VARCHAR NOT NULL,
    alert_type VARCHAR NOT NULL, -- 'MANAGER_CHANGE', 'OBJECTIVE_CHANGE', 'CATEGORY_CHANGE', 'SECTOR_DRIFT', 'NEW_STOCK', 'EXIT_STOCK'
    old_value VARCHAR,
    new_value VARCHAR,
    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE
);

-- Kite Historical Data (OHLCV)
CREATE TABLE IF NOT EXISTS historical_prices (
    symbol VARCHAR NOT NULL,
    price_date DATE NOT NULL,
    open_price DECIMAL(18,4),
    high_price DECIMAL(18,4),
    low_price DECIMAL(18,4),
    close_price DECIMAL(18,4),
    volume BIGINT,
    PRIMARY KEY (symbol, price_date)
);

CREATE TABLE IF NOT EXISTS macro_data (
    date DATE NOT NULL,
    metric VARCHAR NOT NULL,
    value DECIMAL(18,4),
    PRIMARY KEY (date, metric)
);

CREATE TABLE IF NOT EXISTS news_data (
    id VARCHAR PRIMARY KEY,
    date DATE NOT NULL,
    title VARCHAR NOT NULL,
    source VARCHAR,
    description TEXT
);

CREATE TABLE IF NOT EXISTS intelligence_signals (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signal_date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    bucket VARCHAR,
    asset_type VARCHAR,
    dip_pct DECIMAL(8,4),
    momentum VARCHAR,
    momentum_pct DECIMAL(8,4),
    sector_score DECIMAL(5,2),
    macro_fit VARCHAR,
    trailing_stop_status VARCHAR,
    trailing_stop_buffer_pct DECIMAL(8,4),
    composite_signal VARCHAR NOT NULL,
    signal_strength INTEGER,
    reasoning TEXT,
    raw_factors JSON
);

CREATE TABLE IF NOT EXISTS macro_regime_log (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    regime_date DATE NOT NULL,
    regime VARCHAR NOT NULL,
    confidence INTEGER,
    dxy DECIMAL(8,4),
    us10y DECIMAL(8,4),
    brent DECIMAL(8,4),
    yield_spread DECIMAL(8,4),
    fii_net_crore DECIMAL(14,2),
    fii_stance VARCHAR,
    interpretation TEXT,
    raw_signals JSON
);

-- ── Data Layer: Phase 1 additions ──────────────────────────────────────────

-- Tickertape Pro / Screener.in CSV exports — one row per symbol per export
CREATE TABLE IF NOT EXISTS screener_exports (
    id VARCHAR PRIMARY KEY,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR NOT NULL,                   -- 'tickertape' | 'screener_in' | 'manual'
    symbol VARCHAR NOT NULL,
    company_name VARCHAR,
    sector VARCHAR,
    market_cap_cr DECIMAL(18,2),
    pe_ratio DECIMAL(10,4),
    pb_ratio DECIMAL(10,4),
    roce_pct DECIMAL(8,4),
    roe_pct DECIMAL(8,4),
    debt_to_equity DECIMAL(10,4),
    revenue_growth_1y DECIMAL(8,4),
    profit_growth_1y DECIMAL(8,4),
    dividend_yield_pct DECIMAL(8,4),
    score_raw DECIMAL(8,4),                    -- raw screener composite score if present
    export_date DATE NOT NULL,
    raw_row JSON,                              -- full CSV row kept for replay / re-processing
    UNIQUE(symbol, export_date, source)
);

-- Fundamental snapshots — quarterly / annual / TTM per instrument per source
CREATE TABLE IF NOT EXISTS fundamentals (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    period_end DATE NOT NULL,                  -- fiscal quarter-end or year-end date
    period_type VARCHAR NOT NULL,              -- 'quarterly' | 'annual' | 'ttm'
    source VARCHAR NOT NULL,                   -- 'tickertape' | 'yfinance' | 'manual'
    revenue_cr DECIMAL(18,2),
    net_profit_cr DECIMAL(18,2),
    ebitda_cr DECIMAL(18,2),
    eps DECIMAL(10,4),
    book_value_per_share DECIMAL(10,4),
    pe_ratio DECIMAL(10,4),
    pb_ratio DECIMAL(10,4),
    roce_pct DECIMAL(8,4),
    roe_pct DECIMAL(8,4),
    debt_to_equity DECIMAL(10,4),
    current_ratio DECIMAL(10,4),
    promoter_holding_pct DECIMAL(8,4),
    fii_holding_pct DECIMAL(8,4),
    raw_data JSON,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, period_end, period_type, source)
);
