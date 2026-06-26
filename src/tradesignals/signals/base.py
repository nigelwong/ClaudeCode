from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class FundamentalData:
    """Institutional 13F holdings and Form 4 insider transactions. Callers
    (the backtest engine, the daily CLI run) are responsible for fetching
    these already filtered to rows visible as of a given date -- gated on
    filed_date, per db/repository.py and CLAUDE.md's no-lookahead
    invariant. Strategy implementations trust that contract rather than
    re-checking it."""

    institutional_holdings: pd.DataFrame
    insider_transactions: pd.DataFrame


@dataclass
class ScoreComponents:
    score: float  # roughly in [-1, 1]; positive = long lean, negative = short lean
    details: dict = field(default_factory=dict)  # raw inputs, for explainability


class Strategy(ABC):
    """Turns point-in-time data into a per-ticker score. `market_data` and
    `fundamental_data` are guaranteed by the caller to contain no rows
    beyond `as_of_date` -- see FundamentalData's docstring."""

    name: str
    required_lookback_days: int

    @abstractmethod
    def score(
        self,
        as_of_date: date,
        market_data: pd.DataFrame,
        fundamental_data: FundamentalData,
    ) -> dict[str, ScoreComponents]:
        ...
