from datetime import date

import pytest

from tradesignals.regime.composite import compute_market_outlook
from tradesignals.regime.risk_tilt import RiskTilt
from tradesignals.regime.sector_rank import SectorTier
from tradesignals.regime.trend import TrendRegime
from tradesignals.regime.volatility import StressLevel

AS_OF = date(2024, 1, 2)

# (case_id, trend, breadth, volatility, yield_curve_inverted, risk_tilt, expected_overall_regime)
_CASES = [
    (
        "bull_calm_stays_bull",
        TrendRegime.BULL, 0.8, StressLevel.LOW, False, RiskTilt.RISK_ON,
        TrendRegime.BULL,
    ),
    (
        "high_vol_escalates_to_correction_watch",
        TrendRegime.BULL, 0.8, StressLevel.HIGH, False, RiskTilt.RISK_ON,
        TrendRegime.CORRECTION_WATCH,
    ),
    (
        "inverted_curve_escalates_to_correction_watch",
        TrendRegime.BULL, 0.8, StressLevel.LOW, True, RiskTilt.RISK_ON,
        TrendRegime.CORRECTION_WATCH,
    ),
    (
        "weak_breadth_escalates_to_neutral",
        TrendRegime.BULL, 0.3, StressLevel.LOW, False, RiskTilt.RISK_ON,
        TrendRegime.NEUTRAL,
    ),
    (
        "risk_off_escalates_to_neutral",
        TrendRegime.BULL, 0.8, StressLevel.LOW, False, RiskTilt.RISK_OFF,
        TrendRegime.NEUTRAL,
    ),
    (
        "high_vol_and_risk_off_compound_to_bear",
        TrendRegime.BULL, 0.8, StressLevel.HIGH, False, RiskTilt.RISK_OFF,
        TrendRegime.BEAR,
    ),
    (
        "bear_floor_not_relaxed_by_calm_signals",
        TrendRegime.BEAR, 0.8, StressLevel.LOW, False, RiskTilt.RISK_ON,
        TrendRegime.BEAR,
    ),
    (
        "correction_watch_floor_not_lowered_by_weaker_escalation",
        TrendRegime.CORRECTION_WATCH, 0.3, StressLevel.LOW, False, RiskTilt.RISK_ON,
        TrendRegime.CORRECTION_WATCH,
    ),
    (
        "weak_breadth_and_risk_off_without_high_vol_caps_at_neutral",
        TrendRegime.BULL, 0.3, StressLevel.LOW, False, RiskTilt.RISK_OFF,
        TrendRegime.NEUTRAL,
    ),
    (
        "breadth_exactly_at_threshold_is_not_weak",
        TrendRegime.BULL, 0.40, StressLevel.LOW, False, RiskTilt.RISK_ON,
        TrendRegime.BULL,
    ),
]


@pytest.mark.parametrize(
    "trend,breadth,volatility,yield_curve_inverted,risk_tilt,expected",
    [case[1:] for case in _CASES],
    ids=[case[0] for case in _CASES],
)
def test_escalation_rules(trend, breadth, volatility, yield_curve_inverted, risk_tilt, expected):
    outlook = compute_market_outlook(
        as_of_date=AS_OF,
        trend=trend,
        breadth=breadth,
        volatility=volatility,
        yield_curve_inverted=yield_curve_inverted,
        risk_tilt=risk_tilt,
        sector_tiers={},
    )
    assert outlook.overall_regime == expected


def test_sub_signals_pass_through_unchanged():
    sector_tiers = {"XLK": SectorTier.OVERWEIGHT, "XLE": SectorTier.UNDERWEIGHT}
    outlook = compute_market_outlook(
        as_of_date=AS_OF,
        trend=TrendRegime.NEUTRAL,
        breadth=0.55,
        volatility=StressLevel.ELEVATED,
        yield_curve_inverted=True,
        risk_tilt=RiskTilt.RISK_OFF,
        sector_tiers=sector_tiers,
    )
    assert outlook.trend == TrendRegime.NEUTRAL
    assert outlook.breadth == 0.55
    assert outlook.volatility == StressLevel.ELEVATED
    assert outlook.risk_tilt == RiskTilt.RISK_OFF
    assert outlook.sector_tiers == sector_tiers
    assert outlook.as_of_date == AS_OF
    assert outlook.details == {"yield_curve_inverted": True}
