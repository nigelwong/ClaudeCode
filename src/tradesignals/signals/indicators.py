import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """SMA-based RSI (a.k.a. Cutler's RSI), not Wilder's recursively-smoothed
    variant -- chosen so values are exactly hand-computable in unit tests.
    Values will differ slightly from Wilder's RSI (e.g. as reported by most
    charting platforms) for the same input series."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))
    result = result.where(avg_loss != 0, 100.0)  # all gains, no losses -> max strength
    result = result.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)  # flat price -> neutral
    return result
