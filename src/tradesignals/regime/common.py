import pandas as pd


def trailing_return(bars: pd.DataFrame, ticker: str, lookback_days: int) -> float | None:
    """bars: full multi-ticker bars frame, columns ticker/date/close,
    already filtered to <= as_of_date. Returns the close-to-close return
    over the trailing `lookback_days` trading days, or None if there
    isn't enough history yet for this ticker."""
    closes = bars.loc[bars["ticker"] == ticker].sort_values("date")["close"].reset_index(drop=True)
    if len(closes) < lookback_days + 1:
        return None
    return float(closes.iloc[-1] / closes.iloc[-(lookback_days + 1)] - 1)


def latest_value(series: pd.DataFrame) -> float | None:
    """series: columns date/value (a macro_series slice), already filtered
    to <= as_of_date, sorted or not."""
    if series.empty:
        return None
    return float(series.sort_values("date")["value"].iloc[-1])


def value_n_days_ago(series: pd.DataFrame, n: int) -> float | None:
    if series.empty:
        return None
    values = series.sort_values("date")["value"].reset_index(drop=True)
    if len(values) < n + 1:
        return None
    return float(values.iloc[-(n + 1)])
