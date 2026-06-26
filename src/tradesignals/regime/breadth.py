import pandas as pd

from tradesignals.signals.indicators import sma

_MA_WINDOW = 50


def compute_breadth(bars: pd.DataFrame, tickers: list[str]) -> float:
    """bars: full multi-ticker bars frame, columns ticker/date/close,
    already filtered to <= as_of_date. Returns the fraction (0-1) of
    `tickers` whose latest close is above their own 50dma -- a
    participation proxy: a falling benchmark with broad participation
    reads differently than one where breadth has already collapsed.

    Returns 0.5 (neutral) if no ticker has enough history yet, so an
    early/sparse cache doesn't masquerade as a real breadth signal.
    """
    above, counted = 0, 0
    for ticker in tickers:
        closes = bars.loc[bars["ticker"] == ticker].sort_values("date")["close"].reset_index(drop=True)
        if len(closes) < _MA_WINDOW:
            continue
        sma50 = sma(closes, _MA_WINDOW)
        latest_sma = sma50.iloc[-1]
        if pd.isna(latest_sma):
            continue
        counted += 1
        if closes.iloc[-1] > latest_sma:
            above += 1
    if counted == 0:
        return 0.5
    return above / counted
