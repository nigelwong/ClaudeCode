from enum import Enum

import pandas as pd

from tradesignals.regime.common import trailing_return

_DEFAULT_LOOKBACK_DAYS = 63  # ~1 trading quarter


class SectorTier(str, Enum):
    OVERWEIGHT = "overweight"
    NEUTRAL = "neutral"
    UNDERWEIGHT = "underweight"


def rank_sectors(
    bars: pd.DataFrame,
    sector_tickers: list[str],
    benchmark_ticker: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> dict[str, SectorTier]:
    """bars: full multi-ticker bars frame, already filtered to <=
    as_of_date. Ranks each sector ETF's trailing return relative to
    `benchmark_ticker`'s return over the same window -- relative to "the
    market", the same baseline a trader actually compares sector
    performance against, not equal-weight or each sector's own history.
    Top third -> OVERWEIGHT, bottom third -> UNDERWEIGHT, middle ->
    NEUTRAL. Sectors without enough history default to NEUTRAL.
    """
    tiers = {ticker: SectorTier.NEUTRAL for ticker in sector_tickers}

    benchmark_return = trailing_return(bars, benchmark_ticker, lookback_days)
    if benchmark_return is None:
        return tiers

    relative_strength: dict[str, float] = {}
    for ticker in sector_tickers:
        sector_return = trailing_return(bars, ticker, lookback_days)
        if sector_return is None:
            continue
        relative_strength[ticker] = sector_return - benchmark_return

    if not relative_strength:
        return tiers

    ranked = sorted(relative_strength, key=lambda t: relative_strength[t], reverse=True)
    n = len(ranked)
    top_cut = max(1, n // 3)
    bottom_cut = max(0, min(max(1, n // 3), n - top_cut))

    for ticker in ranked[:top_cut]:
        tiers[ticker] = SectorTier.OVERWEIGHT
    if bottom_cut:
        for ticker in ranked[-bottom_cut:]:
            tiers[ticker] = SectorTier.UNDERWEIGHT
    return tiers
