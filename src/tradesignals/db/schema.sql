CREATE TABLE IF NOT EXISTS bars (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    adj_close REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);

-- 13F institutional holdings. report_period is the quarter-end the holding
-- reflects; filed_date is when it actually became public on EDGAR (up to
-- ~45 days later). Any point-in-time logic MUST gate on filed_date, never
-- report_period, or it commits lookahead bias.
CREATE TABLE IF NOT EXISTS institutional_holdings (
    cik TEXT NOT NULL,
    filer_name TEXT NOT NULL,
    cusip TEXT NOT NULL,
    ticker TEXT,
    report_period TEXT NOT NULL,
    filed_date TEXT NOT NULL,
    shares INTEGER NOT NULL,
    value_usd INTEGER NOT NULL,
    PRIMARY KEY (cik, cusip, report_period)
);

-- Form 4 insider transactions. transaction_date is when the trade
-- happened; filed_date is when it posted on EDGAR. Gate on filed_date for
-- the same reason as institutional_holdings.
CREATE TABLE IF NOT EXISTS insider_transactions (
    cik TEXT NOT NULL,
    ticker TEXT NOT NULL,
    insider_name TEXT NOT NULL,
    insider_title TEXT,
    transaction_date TEXT NOT NULL,
    filed_date TEXT NOT NULL,
    transaction_code TEXT NOT NULL,
    shares REAL NOT NULL,
    price REAL,
    shares_owned_after REAL,
    PRIMARY KEY (cik, ticker, transaction_date, insider_name, transaction_code, shares)
);

CREATE TABLE IF NOT EXISTS signals (
    run_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    score REAL NOT NULL,
    rank INTEGER NOT NULL,
    components_json TEXT NOT NULL,
    PRIMARY KEY (run_date, ticker, strategy_name)
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    params_json TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    is_oos INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    run_id TEXT NOT NULL REFERENCES backtest_runs (run_id),
    ticker TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    exit_date TEXT,
    entry_price REAL NOT NULL,
    exit_price REAL,
    side TEXT NOT NULL,
    pnl REAL,
    pnl_pct REAL
);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    run_id TEXT PRIMARY KEY REFERENCES backtest_runs (run_id),
    total_return REAL NOT NULL,
    annualized_return REAL NOT NULL,
    win_rate REAL NOT NULL,
    sharpe REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    benchmark_total_return REAL NOT NULL,
    benchmark_sharpe REAL NOT NULL
);
