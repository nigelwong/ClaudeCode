import math

import pandas as pd
import pytest

from tradesignals.signals.indicators import ema, rsi, sma


def test_sma_hand_computed():
    series = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0, 14.0])
    result = sma(series, window=3)
    expected = [None, None, 11.0, 11.0 + 1 / 3, 12.0, 12.0 + 2 / 3]
    for actual, exp in zip(result, expected):
        if exp is None:
            assert math.isnan(actual)
        else:
            assert actual == pytest.approx(exp)


def test_ema_matches_recursive_formula_with_adjust_false():
    series = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0, 14.0])
    span = 3
    alpha = 2 / (span + 1)

    expected = [series.iloc[0]]
    for value in series.iloc[1:]:
        expected.append(alpha * value + (1 - alpha) * expected[-1])

    result = ema(series, span=span)
    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    for i in range(2, len(series)):
        assert result.iloc[i] == pytest.approx(expected[i])


def test_rsi_all_gains_is_max_strength():
    series = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
    result = rsi(series, period=3)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_flat_price_is_neutral():
    series = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
    result = rsi(series, period=3)
    assert result.iloc[-1] == pytest.approx(50.0)


def test_rsi_mixed_gains_and_losses_hand_computed():
    # deltas: +4, -2, +4 -> gain=[4,0,4] (mean 8/3), loss=[0,2,0] (mean 2/3)
    # rs = (8/3)/(2/3) = 4 -> rsi = 100 - 100/(1+4) = 80
    series = pd.Series([100.0, 104.0, 102.0, 106.0])
    result = rsi(series, period=3)
    assert result.iloc[-1] == pytest.approx(80.0)
