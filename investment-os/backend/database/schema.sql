CREATE TABLE IF NOT EXISTS holdings (
    id VARCHAR PRIMARY KEY,
    asset_name VARCHAR NOT NULL,
    ticker VARCHAR,
    asset_class VARCHAR NOT NULL,
    sub_class VARCHAR,
    source VARCHAR NOT NULL,
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
