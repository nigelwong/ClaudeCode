from datetime import date

import pandas as pd

from tradesignals.signals.base import FundamentalData, ScoreComponents, Strategy


class VolumeBreakoutStrategy(Strategy):
    """Long lean on a price breakout above the N-day high accompanied by
    above-average volume; short lean on the symmetric breakdown below the
    N-day low. Zero otherwise."""

    name = "volume_breakout"

    def __init__(self, breakout_window: int = 20, volume_multiple: float = 1.5):
        self.breakout_window = breakout_window
        self.volume_multiple = volume_multiple
        self.required_lookback_days = breakout_window + 5

    def score(
        self, as_of_date: date, market_data: pd.DataFrame, fundamental_data: FundamentalData
    ) -> dict[str, ScoreComponents]:
        results: dict[str, ScoreComponents] = {}
        for ticker, group in market_data.groupby("ticker"):
            group = group.sort_values("date")
            if len(group) < self.breakout_window + 1:
                continue
            prior, latest = group.iloc[:-1], group.iloc[-1]
            prior_high = prior["close"].tail(self.breakout_window).max()
            prior_low = prior["close"].tail(self.breakout_window).min()
            avg_volume = prior["volume"].tail(self.breakout_window).mean()
            if prior_high == 0 or prior_low == 0 or avg_volume == 0:
                continue

            volume_ratio = latest["volume"] / avg_volume
            breakout_pct = (latest["close"] - prior_high) / prior_high
            breakdown_pct = (latest["close"] - prior_low) / prior_low

            score = 0.0
            if breakout_pct > 0 and volume_ratio >= self.volume_multiple:
                score = max(-1.0, min(1.0, breakout_pct * 5))
            elif breakdown_pct < 0 and volume_ratio >= self.volume_multiple:
                score = max(-1.0, min(1.0, breakdown_pct * 5))

            results[ticker] = ScoreComponents(
                score=score,
                details={
                    "breakout_pct": round(float(breakout_pct) * 100, 2),
                    "breakdown_pct": round(float(breakdown_pct) * 100, 2),
                    "volume_ratio": round(float(volume_ratio), 2),
                },
            )
        return results
