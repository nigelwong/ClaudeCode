from datetime import date

import pandas as pd
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from tradesignals.config import Settings


class AlpacaBarClient:
    """Thin wrapper around alpaca-py's free-tier (IEX feed) daily bars."""

    def __init__(self, settings: Settings):
        self._client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)

    def fetch_daily_bars(self, tickers: list[str], start: date, end: date) -> pd.DataFrame:
        """Returns columns: ticker, date, open, high, low, close, volume, adj_close.

        Uses the free IEX feed (not SIP) and requests split/dividend-adjusted
        prices explicitly, since unadjusted prices across a split would
        produce nonsensical signal spikes for momentum/MA strategies.
        """
        request = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
            adjustment=Adjustment.ALL,
        )
        bar_set = self._client.get_stock_bars(request)
        df = bar_set.df
        if df.empty:
            return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"])

        df = df.reset_index().rename(columns={"symbol": "ticker", "timestamp": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date
        # adjustment=ALL already applies splits/dividends to OHLC; adj_close
        # mirrors close so downstream code has one column name to rely on.
        df["adj_close"] = df["close"]
        return df[["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]]
