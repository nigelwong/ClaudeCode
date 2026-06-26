from datetime import date

import pandas as pd

from tradesignals.signals.base import FundamentalData, ScoreComponents, Strategy
from tradesignals.signals.indicators import sma


class MovingAverageCrossoverStrategy(Strategy):
    """Long lean when the short MA sits above the long MA (golden cross
    territory), short lean when below, scaled by the spread between them."""

    name = "ma_crossover"

    def __init__(self, short_window: int = 20, long_window: int = 50):
        self.short_window = short_window
        self.long_window = long_window
        self.required_lookback_days = long_window + 5

    def score(
        self, as_of_date: date, market_data: pd.DataFrame, fundamental_data: FundamentalData
    ) -> dict[str, ScoreComponents]:
        results: dict[str, ScoreComponents] = {}
        for ticker, group in market_data.groupby("ticker"):
            group = group.sort_values("date")
            if len(group) < self.long_window:
                continue
            short_ma = sma(group["close"], self.short_window).iloc[-1]
            long_ma = sma(group["close"], self.long_window).iloc[-1]
            if pd.isna(short_ma) or pd.isna(long_ma) or long_ma == 0:
                continue
            spread = (short_ma - long_ma) / long_ma
            # A 10% spread maps to a full-strength +/-1 score.
            score = max(-1.0, min(1.0, spread * 10))
            results[ticker] = ScoreComponents(
                score=score,
                details={"short_ma": round(float(short_ma), 2), "long_ma": round(float(long_ma), 2)},
            )
        return results
