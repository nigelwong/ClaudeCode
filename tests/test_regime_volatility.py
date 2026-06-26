import pandas as pd

from tradesignals.regime.volatility import StressLevel, classify_volatility


def _series(values: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(values))
    return pd.DataFrame({"date": dates, "value": values})


def test_all_calm_is_low():
    vix = _series([15.0])
    yield_curve = _series([1.0])
    credit_spread = _series([3.0] * 21)
    level, details = classify_volatility(vix, yield_curve, credit_spread)
    assert level == StressLevel.LOW
    assert details["yield_curve_inverted"] is False
    assert details["credit_spread_widening"] is False


def test_vix_high_is_high():
    vix = _series([35.0])
    yield_curve = _series([1.0])
    credit_spread = _series([3.0] * 21)
    level, _ = classify_volatility(vix, yield_curve, credit_spread)
    assert level == StressLevel.HIGH


def test_vix_elevated_alone_is_elevated():
    vix = _series([25.0])
    yield_curve = _series([1.0])
    credit_spread = _series([3.0] * 21)
    level, _ = classify_volatility(vix, yield_curve, credit_spread)
    assert level == StressLevel.ELEVATED


def test_inverted_yield_curve_alone_is_elevated():
    vix = _series([15.0])
    yield_curve = _series([-0.1])
    credit_spread = _series([3.0] * 21)
    level, details = classify_volatility(vix, yield_curve, credit_spread)
    assert level == StressLevel.ELEVATED
    assert details["yield_curve_inverted"] is True


def test_widening_credit_spread_alone_is_elevated():
    vix = _series([15.0])
    yield_curve = _series([1.0])
    credit_spread = _series([3.0] * 20 + [3.6])
    level, details = classify_volatility(vix, yield_curve, credit_spread)
    assert level == StressLevel.ELEVATED
    assert details["credit_spread_widening"] is True


def test_high_vix_dominates_combined_signals():
    vix = _series([35.0])
    yield_curve = _series([-0.1])
    credit_spread = _series([3.0] * 20 + [3.6])
    level, _ = classify_volatility(vix, yield_curve, credit_spread)
    assert level == StressLevel.HIGH
