from enum import Enum

import pandas as pd

from tradesignals.regime.common import latest_value, value_n_days_ago

VIX_ELEVATED_THRESHOLD = 20.0
VIX_HIGH_THRESHOLD = 30.0
CREDIT_SPREAD_WIDENING_PP = 0.5  # percentage-point widening over the lookback to count as stress
_CREDIT_SPREAD_LOOKBACK_DAYS = 20

_SEVERITY = {"low": 0, "elevated": 1, "high": 2}


class StressLevel(str, Enum):
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"


def _max_level(a: StressLevel, b: StressLevel) -> StressLevel:
    return a if _SEVERITY[a.value] >= _SEVERITY[b.value] else b


def classify_volatility(
    vix: pd.DataFrame, yield_curve: pd.DataFrame, credit_spread: pd.DataFrame
) -> tuple[StressLevel, dict]:
    """vix, yield_curve, credit_spread: columns date/value (macro_series
    slices for VIXCLS, T10Y2Y, BAMLH0A0HYM2 respectively), already
    filtered to <= as_of_date. Combines VIX level, yield-curve inversion,
    and credit-spread widening into one StressLevel, plus a details dict
    surfacing each sub-component for explainability and for composite.py's
    escalation logic (which needs yield_curve_inverted specifically)."""
    level = StressLevel.LOW
    details: dict = {}

    vix_now = latest_value(vix)
    details["vix"] = vix_now
    if vix_now is not None and vix_now >= VIX_HIGH_THRESHOLD:
        level = _max_level(level, StressLevel.HIGH)
    elif vix_now is not None and vix_now >= VIX_ELEVATED_THRESHOLD:
        level = _max_level(level, StressLevel.ELEVATED)

    curve_now = latest_value(yield_curve)
    inverted = curve_now is not None and curve_now <= 0
    details["yield_curve"] = curve_now
    details["yield_curve_inverted"] = inverted
    if inverted:
        level = _max_level(level, StressLevel.ELEVATED)

    spread_now = latest_value(credit_spread)
    spread_then = value_n_days_ago(credit_spread, _CREDIT_SPREAD_LOOKBACK_DAYS)
    widening = (
        spread_now is not None and spread_then is not None and (spread_now - spread_then) >= CREDIT_SPREAD_WIDENING_PP
    )
    details["credit_spread"] = spread_now
    details["credit_spread_widening"] = widening
    if widening:
        level = _max_level(level, StressLevel.ELEVATED)

    return level, details
