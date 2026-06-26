import pandas as pd

from tradesignals.regime.sector_rank import SectorTier, rank_sectors


def _bars_for(ticker: str, first_close: float, last_close: float, periods: int = 6) -> pd.DataFrame:
    closes = [first_close] * (periods - 1) + [last_close]
    dates = pd.bdate_range("2020-01-01", periods=periods)
    return pd.DataFrame({"ticker": ticker, "date": dates, "close": closes})


def test_ranks_sectors_relative_to_benchmark():
    # benchmark return = +0.05; sector returns chosen so relative strength
    # (sector_return - benchmark_return) is distinct and ordered per sector.
    benchmark = _bars_for("SPY", 100, 105)
    s1 = _bars_for("S1", 100, 120)  # return .20 -> relative +.15 (top)
    s2 = _bars_for("S2", 100, 115)  # return .15 -> relative +.10 (top)
    s3 = _bars_for("S3", 100, 107)  # return .07 -> relative +.02 (middle)
    s4 = _bars_for("S4", 100, 104)  # return .04 -> relative -.01 (middle)
    s5 = _bars_for("S5", 100, 97)  # return -.03 -> relative -.08 (bottom)
    s6 = _bars_for("S6", 100, 93)  # return -.07 -> relative -.12 (bottom)
    s7 = _bars_for("S7", 100, 200, periods=3)  # insufficient history -> default neutral

    bars = pd.concat([benchmark, s1, s2, s3, s4, s5, s6, s7], ignore_index=True)
    tiers = rank_sectors(bars, ["S1", "S2", "S3", "S4", "S5", "S6", "S7"], "SPY", lookback_days=5)

    assert tiers["S1"] == SectorTier.OVERWEIGHT
    assert tiers["S2"] == SectorTier.OVERWEIGHT
    assert tiers["S3"] == SectorTier.NEUTRAL
    assert tiers["S4"] == SectorTier.NEUTRAL
    assert tiers["S5"] == SectorTier.UNDERWEIGHT
    assert tiers["S6"] == SectorTier.UNDERWEIGHT
    assert tiers["S7"] == SectorTier.NEUTRAL


def test_missing_benchmark_history_defaults_all_to_neutral():
    s1 = _bars_for("S1", 100, 120)
    s2 = _bars_for("S2", 100, 90)
    bars = pd.concat([s1, s2], ignore_index=True)  # no "SPY" rows at all
    tiers = rank_sectors(bars, ["S1", "S2"], "SPY", lookback_days=5)
    assert tiers == {"S1": SectorTier.NEUTRAL, "S2": SectorTier.NEUTRAL}
