from enum import Enum

import pandas as pd

from tradesignals.signals.indicators import sma

_RISING_LOOKBACK_DAYS = 5  # ~1 trading week, for "is this average rising or falling"


class TrendRegime(str, Enum):
    BULL = "bull"
    NEUTRAL = "neutral"
    CORRECTION_WATCH = "correction_watch"
    BEAR = "bear"


def classify_trend(benchmark_bars: pd.DataFrame) -> TrendRegime:
    """benchmark_bars: columns date, close for the benchmark (e.g. SPY),
    already filtered to <= as_of_date. Needs >= 200 rows for a meaningful
    read; returns NEUTRAL (not a guess) when there isn't enough history.

    Rules, applied in order:
    1. BEAR: price below its 200dma AND the 200dma itself is falling --
       a confirmed downtrend, not just a dip.
    2. CORRECTION_WATCH: price below its 50dma (whether or not the 200dma
       has also been breached) but the 200dma isn't falling -- early
       weakness, not yet a confirmed downtrend.
    3. BULL: price above both its 50dma and 200dma, and the 50dma rising.
    4. NEUTRAL: everything else (e.g. chopping around a flat average).
    """
    closes = benchmark_bars.sort_values("date")["close"].reset_index(drop=True)
    if len(closes) < 200 + _RISING_LOOKBACK_DAYS:
        return TrendRegime.NEUTRAL

    sma50 = sma(closes, 50)
    sma200 = sma(closes, 200)
    price = closes.iloc[-1]
    sma50_now, sma50_prev = sma50.iloc[-1], sma50.iloc[-1 - _RISING_LOOKBACK_DAYS]
    sma200_now, sma200_prev = sma200.iloc[-1], sma200.iloc[-1 - _RISING_LOOKBACK_DAYS]

    below_50 = price < sma50_now
    below_200 = price < sma200_now
    sma50_rising = sma50_now > sma50_prev
    sma200_falling = sma200_now < sma200_prev

    if below_200 and sma200_falling:
        return TrendRegime.BEAR
    if below_50:
        return TrendRegime.CORRECTION_WATCH
    if not below_200 and sma50_rising:
        return TrendRegime.BULL
    return TrendRegime.NEUTRAL
