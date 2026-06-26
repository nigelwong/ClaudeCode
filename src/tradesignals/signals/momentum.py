from datetime import date

import pandas as pd

from tradesignals.signals.base import FundamentalData, ScoreComponents, Strategy
from tradesignals.signals.indicators import rsi


class MomentumRSIStrategy(Strategy):
    """Classic RSI mean-reversion: long lean when oversold, short lean when
    overbought, scaled continuously between."""

    name = "momentum"

    def __init__(self, rsi_period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.required_lookback_days = rsi_period + 5

    def score(
        self, as_of_date: date, market_data: pd.DataFrame, fundamental_data: FundamentalData
    ) -> dict[str, ScoreComponents]:
        results: dict[str, ScoreComponents] = {}
        for ticker, group in market_data.groupby("ticker"):
            group = group.sort_values("date")
            if len(group) < self.rsi_period + 1:
                continue
            latest_rsi = rsi(group["close"], self.rsi_period).iloc[-1]
            if pd.isna(latest_rsi):
                continue
            score = max(-1.0, min(1.0, (50.0 - latest_rsi) / 50.0))
            results[ticker] = ScoreComponents(
                score=score,
                details={
                    "rsi": round(float(latest_rsi), 2),
                    "oversold": bool(latest_rsi <= self.oversold),
                    "overbought": bool(latest_rsi >= self.overbought),
                },
            )
        return results
