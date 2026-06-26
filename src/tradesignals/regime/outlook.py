from datetime import date

import pandas as pd

from tradesignals.data.fred_client import MACRO_SERIES
from tradesignals.regime.breadth import compute_breadth
from tradesignals.regime.composite import MarketOutlook, compute_market_outlook
from tradesignals.regime.risk_tilt import classify_risk_tilt
from tradesignals.regime.sector_rank import rank_sectors
from tradesignals.regime.trend import classify_trend
from tradesignals.regime.volatility import classify_volatility


def compute_outlook(
    bars: pd.DataFrame,
    macro_series: pd.DataFrame,
    benchmark_ticker: str,
    breadth_tickers: list[str],
    sector_tickers: list[str],
    bonds_ticker: str,
    gold_ticker: str,
    as_of_date: date,
) -> MarketOutlook:
    """Runs all five regime sub-signals against `bars`/`macro_series` --
    both expected already filtered to <= as_of_date by the caller, same
    no-lookahead contract as signals/base.py -- and combines them into
    one MarketOutlook. Shared by the live `market-outlook` CLI command
    and regime_engine.py's per-rebalance decision, so the two can never
    drift out of sync on how a regime call is derived.
    """

    def _macro_slice(role: str) -> pd.DataFrame:
        series_id = MACRO_SERIES[role]
        return macro_series.loc[macro_series["series_id"] == series_id, ["date", "value"]]

    benchmark_bars = bars.loc[bars["ticker"] == benchmark_ticker, ["date", "close"]]
    trend = classify_trend(benchmark_bars)
    breadth = compute_breadth(bars, breadth_tickers)
    volatility, vol_details = classify_volatility(
        _macro_slice("vix"), _macro_slice("yield_curve"), _macro_slice("credit_spread")
    )
    sector_tiers = rank_sectors(bars, sector_tickers, benchmark_ticker)
    risk_tilt = classify_risk_tilt(bars, benchmark_ticker, bonds_ticker, gold_ticker)

    return compute_market_outlook(
        as_of_date=as_of_date,
        trend=trend,
        breadth=breadth,
        volatility=volatility,
        yield_curve_inverted=bool(vol_details.get("yield_curve_inverted", False)),
        risk_tilt=risk_tilt,
        sector_tiers=sector_tiers,
    )
