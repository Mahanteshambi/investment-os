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
