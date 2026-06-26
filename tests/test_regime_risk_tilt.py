import pandas as pd

from tradesignals.regime.risk_tilt import RiskTilt, classify_risk_tilt


def _bars_for(ticker: str, first_close: float, last_close: float, periods: int = 6) -> pd.DataFrame:
    closes = [first_close] * (periods - 1) + [last_close]
    dates = pd.bdate_range("2020-01-01", periods=periods)
    return pd.DataFrame({"ticker": ticker, "date": dates, "close": closes})


def _classify(equity, bonds, gold):
    bars = pd.concat([equity, bonds, gold], ignore_index=True)
    return classify_risk_tilt(bars, "SPY", "TLT", "GLD", lookback_days=5)


def test_equities_outperforming_safe_havens_is_risk_on():
    equity = _bars_for("SPY", 100, 110)  # +.10
    bonds = _bars_for("TLT", 100, 102)  # +.02
    gold = _bars_for("GLD", 100, 101)  # +.01
    assert _classify(equity, bonds, gold) == RiskTilt.RISK_ON


def test_safe_havens_outperforming_equities_is_risk_off():
    equity = _bars_for("SPY", 100, 101)  # +.01
    bonds = _bars_for("TLT", 100, 105)  # +.05
    gold = _bars_for("GLD", 100, 106)  # +.06
    assert _classify(equity, bonds, gold) == RiskTilt.RISK_OFF


def test_small_spread_is_neutral():
    equity = _bars_for("SPY", 100, 105)  # +.05
    bonds = _bars_for("TLT", 100, 104)  # +.04
    gold = _bars_for("GLD", 100, 103)  # +.03
    assert _classify(equity, bonds, gold) == RiskTilt.NEUTRAL


def test_missing_history_defaults_to_neutral():
    equity = _bars_for("SPY", 100, 110)
    bonds = _bars_for("TLT", 100, 102, periods=3)  # insufficient history
    gold = _bars_for("GLD", 100, 101)
    assert _classify(equity, bonds, gold) == RiskTilt.NEUTRAL


def test_spread_exactly_at_margin_is_risk_on():
    equity = _bars_for("SPY", 100, 108)  # +.08
    bonds = _bars_for("TLT", 100, 105)  # +.05
    gold = _bars_for("GLD", 100, 104)  # +.04 -> safe haven .05, spread = .03
    assert _classify(equity, bonds, gold) == RiskTilt.RISK_ON


def test_spread_exactly_at_negative_margin_is_risk_off():
    equity = _bars_for("SPY", 100, 105)  # +.05
    bonds = _bars_for("TLT", 100, 108)  # +.08
    gold = _bars_for("GLD", 100, 107)  # +.07 -> safe haven .08, spread = -.03
    assert _classify(equity, bonds, gold) == RiskTilt.RISK_OFF
