from dataclasses import dataclass, field
from datetime import date

from tradesignals.regime.risk_tilt import RiskTilt
from tradesignals.regime.sector_rank import SectorTier
from tradesignals.regime.trend import TrendRegime
from tradesignals.regime.volatility import StressLevel

BREADTH_WEAK_THRESHOLD = 0.40

_SEVERITY = {
    TrendRegime.BULL: 0,
    TrendRegime.NEUTRAL: 1,
    TrendRegime.CORRECTION_WATCH: 2,
    TrendRegime.BEAR: 3,
}


@dataclass
class MarketOutlook:
    as_of_date: date
    overall_regime: TrendRegime
    trend: TrendRegime
    breadth: float
    volatility: StressLevel
    risk_tilt: RiskTilt
    sector_tiers: dict[str, SectorTier]
    details: dict = field(default_factory=dict)


def _escalate(regime: TrendRegime, floor: TrendRegime) -> TrendRegime:
    return regime if _SEVERITY[regime] >= _SEVERITY[floor] else floor


def compute_market_outlook(
    as_of_date: date,
    trend: TrendRegime,
    breadth: float,
    volatility: StressLevel,
    yield_curve_inverted: bool,
    risk_tilt: RiskTilt,
    sector_tiers: dict[str, SectorTier],
) -> MarketOutlook:
    """Combines the five regime sub-signals into one overall call, per the
    user's lean-cautious decision: a single serious warning sign can pull
    the call toward caution even when price trend alone looks calm, but
    calm price action can never override a real stress signal. Implemented
    as severity-floor escalation (only ever raises the floor, never lowers
    it), not an averaged/weighted blend:

      BULL(0) < NEUTRAL(1) < CORRECTION_WATCH(2) < BEAR(3)

    - `trend` sets the floor.
    - volatility == HIGH, or an inverted yield curve, each escalate the
      floor to at least CORRECTION_WATCH.
    - breadth below BREADTH_WEAK_THRESHOLD, or risk_tilt == RISK_OFF, each
      escalate the floor to at least NEUTRAL.
    - volatility == HIGH together with risk_tilt == RISK_OFF escalate the
      floor to at least BEAR -- compounding warning signs escalate
      further than either alone.

    Sector tiers and risk tilt are surfaced separately for "what to
    rotate into" guidance, not collapsed into the single regime scalar.
    """
    regime = trend

    if volatility == StressLevel.HIGH:
        regime = _escalate(regime, TrendRegime.CORRECTION_WATCH)
    if yield_curve_inverted:
        regime = _escalate(regime, TrendRegime.CORRECTION_WATCH)
    if breadth < BREADTH_WEAK_THRESHOLD:
        regime = _escalate(regime, TrendRegime.NEUTRAL)
    if risk_tilt == RiskTilt.RISK_OFF:
        regime = _escalate(regime, TrendRegime.NEUTRAL)
    if volatility == StressLevel.HIGH and risk_tilt == RiskTilt.RISK_OFF:
        regime = _escalate(regime, TrendRegime.BEAR)

    return MarketOutlook(
        as_of_date=as_of_date,
        overall_regime=regime,
        trend=trend,
        breadth=breadth,
        volatility=volatility,
        risk_tilt=risk_tilt,
        sector_tiers=sector_tiers,
        details={"yield_curve_inverted": yield_curve_inverted},
    )
