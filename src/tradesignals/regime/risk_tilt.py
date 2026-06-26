from enum import Enum

import pandas as pd

from tradesignals.regime.common import trailing_return

_DEFAULT_LOOKBACK_DAYS = 63  # ~1 trading quarter
_TILT_MARGIN = 0.03  # 3pp of relative trailing return to call a tilt, vs. noise


class RiskTilt(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"


def classify_risk_tilt(
    bars: pd.DataFrame,
    equity_ticker: str,
    bonds_ticker: str,
    gold_ticker: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> RiskTilt:
    """bars: full multi-ticker bars frame, already filtered to <=
    as_of_date. Cross-asset momentum: compares the equity benchmark's
    trailing return to the stronger of bonds/gold over the same window.
    Equities meaningfully outperforming the safe havens -> RISK_ON;
    safe havens meaningfully outperforming equities -> RISK_OFF.

    This signal only ever redirects the backtest's *safe* allocation
    bucket (cash vs. bonds/gold) -- it must never directly resize the
    *risky* bucket itself, which stays a function of trend.py alone, to
    keep the two levers orthogonal and the backtest explainable.
    """
    equity_return = trailing_return(bars, equity_ticker, lookback_days)
    bonds_return = trailing_return(bars, bonds_ticker, lookback_days)
    gold_return = trailing_return(bars, gold_ticker, lookback_days)
    if equity_return is None or bonds_return is None or gold_return is None:
        return RiskTilt.NEUTRAL

    safe_haven_return = max(bonds_return, gold_return)
    spread = equity_return - safe_haven_return

    if spread >= _TILT_MARGIN:
        return RiskTilt.RISK_ON
    if spread <= -_TILT_MARGIN:
        return RiskTilt.RISK_OFF
    return RiskTilt.NEUTRAL
