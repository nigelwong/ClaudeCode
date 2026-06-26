import sqlite3
from datetime import date, timedelta

import pandas as pd

from tradesignals.data.alpaca_client import AlpacaBarClient
from tradesignals.db import repository


def get_bars_cached(
    conn: sqlite3.Connection,
    client: AlpacaBarClient,
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """Returns bars for [start, end] across tickers, fetching only the gap
    between what's cached locally and what's requested."""
    missing_tickers: list[str] = []
    fetch_start, fetch_end = start, end

    for ticker in tickers:
        existing_min, existing_max = repository.get_existing_date_range(conn, ticker)
        if existing_min is None:
            missing_tickers.append(ticker)
            continue
        existing_min_d = date.fromisoformat(existing_min)
        existing_max_d = date.fromisoformat(existing_max)
        if start < existing_min_d or end > existing_max_d:
            missing_tickers.append(ticker)

    if missing_tickers:
        fresh = client.fetch_daily_bars(missing_tickers, fetch_start, fetch_end)
        repository.upsert_bars(conn, fresh)

    return repository.get_bars(conn, tickers, start, end)


def trailing_window(as_of: date, lookback_days: int) -> tuple[date, date]:
    """A calendar-day window comfortably covering `lookback_days` of trading
    days (weekends/holidays included in the buffer)."""
    return as_of - timedelta(days=int(lookback_days * 1.6) + 10), as_of
