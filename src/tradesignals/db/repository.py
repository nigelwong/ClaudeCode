import sqlite3
from datetime import date

import pandas as pd


def upsert_bars(conn: sqlite3.Connection, bars: pd.DataFrame) -> None:
    """bars columns: ticker, date, open, high, low, close, volume, adj_close.

    date may be a date/Timestamp or ISO string; normalized to ISO string.
    """
    if bars.empty:
        return
    rows = bars.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
    conn.executemany(
        """
        INSERT INTO bars (ticker, date, open, high, low, close, volume, adj_close)
        VALUES (:ticker, :date, :open, :high, :low, :close, :volume, :adj_close)
        ON CONFLICT (ticker, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume,
            adj_close=excluded.adj_close
        """,
        rows[["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]].to_dict("records"),
    )


def get_bars(
    conn: sqlite3.Connection, tickers: list[str], start: date | None = None, end: date | None = None
) -> pd.DataFrame:
    placeholders = ",".join("?" * len(tickers))
    query = f"SELECT * FROM bars WHERE ticker IN ({placeholders})"
    params: list = list(tickers)
    if start is not None:
        query += " AND date >= ?"
        params.append(start.isoformat())
    if end is not None:
        query += " AND date <= ?"
        params.append(end.isoformat())
    query += " ORDER BY ticker, date"
    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_existing_date_range(conn: sqlite3.Connection, ticker: str) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT MIN(date), MAX(date) FROM bars WHERE ticker = ?", (ticker,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def upsert_macro_series(conn: sqlite3.Connection, series: pd.DataFrame) -> None:
    """series columns: series_id, date, value. date may be a date/Timestamp
    or ISO string; normalized to ISO string."""
    if series.empty:
        return
    rows = series.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.strftime("%Y-%m-%d")
    conn.executemany(
        """
        INSERT INTO macro_series (series_id, date, value)
        VALUES (:series_id, :date, :value)
        ON CONFLICT (series_id, date) DO UPDATE SET value=excluded.value
        """,
        rows[["series_id", "date", "value"]].to_dict("records"),
    )


def get_macro_series(
    conn: sqlite3.Connection, series_id: str, start: date | None = None, end: date | None = None
) -> pd.DataFrame:
    query = "SELECT * FROM macro_series WHERE series_id = ?"
    params: list = [series_id]
    if start is not None:
        query += " AND date >= ?"
        params.append(start.isoformat())
    if end is not None:
        query += " AND date <= ?"
        params.append(end.isoformat())
    query += " ORDER BY date"
    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_existing_macro_date_range(conn: sqlite3.Connection, series_id: str) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT MIN(date), MAX(date) FROM macro_series WHERE series_id = ?", (series_id,)
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def upsert_institutional_holdings(conn: sqlite3.Connection, rows: list[dict]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO institutional_holdings
            (cik, filer_name, cusip, ticker, report_period, filed_date, shares, value_usd)
        VALUES (:cik, :filer_name, :cusip, :ticker, :report_period, :filed_date, :shares, :value_usd)
        ON CONFLICT (cik, cusip, report_period) DO UPDATE SET
            filer_name=excluded.filer_name, ticker=excluded.ticker,
            filed_date=excluded.filed_date, shares=excluded.shares,
            value_usd=excluded.value_usd
        """,
        rows,
    )


def get_institutional_holdings(conn: sqlite3.Connection, as_of_date: date, tickers: list[str]) -> pd.DataFrame:
    """Holdings visible to the market as of as_of_date. Gates on filed_date,
    never report_period, to avoid lookahead bias."""
    placeholders = ",".join("?" * len(tickers))
    query = (
        f"SELECT * FROM institutional_holdings "
        f"WHERE ticker IN ({placeholders}) AND filed_date <= ? "
        f"ORDER BY ticker, report_period"
    )
    return pd.read_sql_query(query, conn, params=[*tickers, as_of_date.isoformat()])


def upsert_insider_transactions(conn: sqlite3.Connection, rows: list[dict]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO insider_transactions
            (cik, ticker, insider_name, insider_title, transaction_date, filed_date,
             transaction_code, shares, price, shares_owned_after)
        VALUES (:cik, :ticker, :insider_name, :insider_title, :transaction_date, :filed_date,
                :transaction_code, :shares, :price, :shares_owned_after)
        ON CONFLICT (cik, ticker, transaction_date, insider_name, transaction_code, shares)
        DO UPDATE SET filed_date=excluded.filed_date, price=excluded.price,
            shares_owned_after=excluded.shares_owned_after
        """,
        rows,
    )


def get_insider_transactions(conn: sqlite3.Connection, as_of_date: date, tickers: list[str]) -> pd.DataFrame:
    """Insider transactions visible to the market as of as_of_date. Gates on
    filed_date, never transaction_date, to avoid lookahead bias."""
    placeholders = ",".join("?" * len(tickers))
    query = (
        f"SELECT * FROM insider_transactions "
        f"WHERE ticker IN ({placeholders}) AND filed_date <= ? "
        f"ORDER BY ticker, transaction_date"
    )
    return pd.read_sql_query(query, conn, params=[*tickers, as_of_date.isoformat()])


def upsert_signals(conn: sqlite3.Connection, rows: list[dict]) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO signals (run_date, ticker, strategy_name, direction, score, rank, components_json)
        VALUES (:run_date, :ticker, :strategy_name, :direction, :score, :rank, :components_json)
        ON CONFLICT (run_date, ticker, strategy_name) DO UPDATE SET
            direction=excluded.direction, score=excluded.score, rank=excluded.rank,
            components_json=excluded.components_json
        """,
        rows,
    )


def get_signals(conn: sqlite3.Connection, run_date: date) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT * FROM signals WHERE run_date = ? ORDER BY rank", conn, params=[run_date.isoformat()]
    )


def insert_backtest_run(
    conn: sqlite3.Connection,
    run_id: str,
    created_at: str,
    strategy_name: str,
    params_json: str,
    start_date: date,
    end_date: date,
    is_oos: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO backtest_runs (run_id, created_at, strategy_name, params_json, start_date, end_date, is_oos)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, created_at, strategy_name, params_json, start_date.isoformat(), end_date.isoformat(), int(is_oos)),
    )


def insert_backtest_trades(conn: sqlite3.Connection, run_id: str, trades: list[dict]) -> None:
    if not trades:
        return
    for t in trades:
        t["run_id"] = run_id
    conn.executemany(
        """
        INSERT INTO backtest_trades
            (run_id, ticker, entry_date, exit_date, entry_price, exit_price, side, pnl, pnl_pct)
        VALUES (:run_id, :ticker, :entry_date, :exit_date, :entry_price, :exit_price, :side, :pnl, :pnl_pct)
        """,
        trades,
    )


def insert_backtest_metrics(conn: sqlite3.Connection, run_id: str, metrics: dict) -> None:
    conn.execute(
        """
        INSERT INTO backtest_metrics
            (run_id, total_return, annualized_return, win_rate, sharpe, max_drawdown,
             benchmark_total_return, benchmark_sharpe)
        VALUES (:run_id, :total_return, :annualized_return, :win_rate, :sharpe, :max_drawdown,
                :benchmark_total_return, :benchmark_sharpe)
        """,
        {"run_id": run_id, **metrics},
    )
