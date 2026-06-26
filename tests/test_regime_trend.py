import pandas as pd

from tradesignals.regime.trend import TrendRegime, classify_trend


def _bars(closes: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"date": dates, "close": closes})


def test_insufficient_history_is_neutral():
    bars = _bars([100.0] * 50)
    assert classify_trend(bars) == TrendRegime.NEUTRAL


def test_steady_uptrend_is_bull():
    closes = [100.0 + i for i in range(220)]
    assert classify_trend(_bars(closes)) == TrendRegime.BULL


def test_steady_downtrend_is_bear():
    closes = [300.0 - i for i in range(220)]
    assert classify_trend(_bars(closes)) == TrendRegime.BEAR


def test_recent_dip_after_long_uptrend_is_correction_watch():
    # 240 days of a strong uptrend, then a sharp 10-day dip. The dip pulls
    # price below the 50dma but is too small a fraction of the 200-day
    # window to turn the 200dma's direction over the rising-lookback,
    # so it reads as early weakness rather than a confirmed downtrend.
    rising = [100.0 + i for i in range(240)]
    dip = [320.0, 300.0, 280.0, 260.0, 240.0, 220.0, 200.0, 180.0, 160.0, 140.0]
    assert classify_trend(_bars(rising + dip)) == TrendRegime.CORRECTION_WATCH


def test_flat_chop_is_neutral():
    closes = [100.0, 101.0] * 110
    assert classify_trend(_bars(closes)) == TrendRegime.NEUTRAL
