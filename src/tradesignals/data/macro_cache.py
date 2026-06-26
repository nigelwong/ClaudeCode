import sqlite3
from datetime import date

import pandas as pd

from tradesignals.data.fred_client import FredClient
from tradesignals.db import repository


def get_macro_series_cached(
    conn: sqlite3.Connection,
    client: FredClient,
    series_id: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Returns macro_series rows for [start, end] for one FRED series,
    fetching only the gap between what's cached locally and what's
    requested -- mirrors data/bar_cache.py's get_bars_cached pattern."""
    existing_min, existing_max = repository.get_existing_macro_date_range(conn, series_id)
    needs_fetch = existing_min is None
    if existing_min is not None:
        existing_min_d = date.fromisoformat(existing_min)
        existing_max_d = date.fromisoformat(existing_max)
        needs_fetch = start < existing_min_d or end > existing_max_d

    if needs_fetch:
        fresh = client.fetch_series(series_id, start, end)
        repository.upsert_macro_series(conn, fresh)

    return repository.get_macro_series(conn, series_id, start, end)
