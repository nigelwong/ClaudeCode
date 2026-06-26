from tradesignals.signals.base import Strategy
from tradesignals.signals.ma_crossover import MovingAverageCrossoverStrategy
from tradesignals.signals.momentum import MomentumRSIStrategy
from tradesignals.signals.volume_breakout import VolumeBreakoutStrategy

# Central registry new strategies get added to. This is the exact extension
# point Phase 2's Model Creator agent will eventually write into -- keep
# this file's shape (a flat name -> class mapping) stable.
STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "momentum": MomentumRSIStrategy,
    "ma_crossover": MovingAverageCrossoverStrategy,
    "volume_breakout": VolumeBreakoutStrategy,
}


def build_strategy(name: str, **params) -> Strategy:
    return STRATEGY_REGISTRY[name](**params)
