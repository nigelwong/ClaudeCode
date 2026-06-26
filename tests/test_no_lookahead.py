from datetime import date

import pandas as pd

from tradesignals.backtest.engine import run_backtest
from tradesignals.signals.base import FundamentalData, ScoreComponents, Strategy
from tradesignals.signals.registry import build_strategy

_EMPTY_HOLDINGS = pd.DataFrame(columns=["ticker", "filed_date"])
_EMPTY_TRANSACTIONS = pd.DataFrame(columns=["ticker", "filed_date"])


class _RecordingStrategy(Strategy):
    """Never trades -- just records what it was shown on each call, so
    tests can assert on visibility directly rather than inferring it from
    trade outcomes."""

    name = "recording"
    required_lookback_days = 0

    def __init__(self):
        self.market_data_calls: dict[date, pd.DataFrame] = {}
        self.fundamental_data_calls: dict[date, FundamentalData] = {}

    def score(
        self, as_of_date: date, market_data: pd.DataFrame, fundamental_data: FundamentalData
    ) -> dict[str, ScoreComponents]:
        self.market_data_calls[as_of_date] = market_data
        self.fundamental_data_calls[as_of_date] = fundamental_data
        return {}


def _bars(ticker: str, dates: list[date], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": 1_000_000,
        }
    )


def test_bars_never_leak_rows_after_as_of_date():
    start, end = date(2024, 3, 1), date(2024, 3, 5)
    in_range_dates = [date(2024, 3, d) for d in range(1, 6)]
    future_dates = [date(2024, 3, d) for d in range(6, 10)]
    # Deliberately extreme future prices -- if they ever leaked in, any
    # rolling/lookback computation reading market_data would be skewed.
    bars = pd.concat(
        [
            _bars("AAPL", in_range_dates, [100.0, 101.0, 102.0, 103.0, 104.0]),
            _bars("AAPL", future_dates, [9999.0, 9999.0, 9999.0, 9999.0]),
        ],
        ignore_index=True,
    )

    strategy = _RecordingStrategy()
    run_backtest(strategy, bars, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, start, end)

    assert set(strategy.market_data_calls.keys()) == set(in_range_dates)
    for as_of_date, market_data in strategy.market_data_calls.items():
        max_visible_date = pd.to_datetime(market_data["date"]).max()
        assert max_visible_date <= pd.Timestamp(as_of_date)
        assert not (market_data["close"] == 9999.0).any()


def test_backtest_output_identical_with_or_without_future_bars():
    start, end = date(2024, 1, 1), date(2024, 4, 1)
    history_start = date(2023, 1, 1)
    history_dates = pd.date_range(history_start, end, freq="D").date.tolist()
    n = len(history_dates)
    # Mildly trending synthetic series so ma_crossover actually trades.
    closes = [100.0 + 0.05 * i for i in range(n)]
    base_bars = _bars("AAPL", history_dates, closes)

    future_dates = pd.date_range(end, periods=30, freq="D").date.tolist()[1:]
    # Wildly different future prices designed to disrupt any lookback
    # window if they were ever visible before their own date.
    future_bars = _bars("AAPL", future_dates, [1.0] * len(future_dates))

    bars_without_future = base_bars
    bars_with_future = pd.concat([base_bars, future_bars], ignore_index=True)

    strategy_a = build_strategy("ma_crossover")
    strategy_b = build_strategy("ma_crossover")

    # A low entry_threshold ensures this mild trend actually triggers a
    # trade -- the point is to compare nontrivial output, not empty runs.
    result_a = run_backtest(
        strategy_a, bars_without_future, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, start, end, entry_threshold=0.05
    )
    result_b = run_backtest(
        strategy_b, bars_with_future, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, start, end, entry_threshold=0.05
    )

    pd.testing.assert_series_equal(result_a.equity_curve, result_b.equity_curve)
    assert len(result_a.trades) == len(result_b.trades)
    for trade_a, trade_b in zip(result_a.trades, result_b.trades):
        assert trade_a == trade_b


def test_institutional_holdings_gated_on_filed_date_not_report_period():
    start, end = date(2024, 4, 1), date(2024, 4, 20)
    bars = _bars("AAPL", pd.date_range(start, end, freq="D").date.tolist(), [100.0] * 20)

    visible_row = {
        "cik": "0001067983",
        "filer_name": "Berkshire Hathaway Inc",
        "cusip": "037833100",
        "ticker": "AAPL",
        "report_period": date(2024, 3, 31),
        "filed_date": date(2024, 4, 10),
        "shares": 1000,
        "value_usd": 100_000,
    }
    # The trap: an old fact date (well before `start`) paired with a
    # filed_date AFTER the whole backtest window -- if the engine
    # mistakenly gated on report_period this row would be visible from
    # day one, which would be lookahead bias.
    trap_row = {
        "cik": "0001037389",
        "filer_name": "Renaissance Technologies LLC",
        "cusip": "037833100",
        "ticker": "AAPL",
        "report_period": date(2023, 12, 31),
        "filed_date": date(2024, 4, 25),
        "shares": 2000,
        "value_usd": 200_000,
    }
    holdings = pd.DataFrame([visible_row, trap_row])

    strategy = _RecordingStrategy()
    run_backtest(strategy, bars, holdings, _EMPTY_TRANSACTIONS, start, end)

    for as_of_date, fundamental_data in strategy.fundamental_data_calls.items():
        seen_filed_dates = set(pd.to_datetime(fundamental_data.institutional_holdings["filed_date"]).dt.date)
        assert date(2024, 4, 25) not in seen_filed_dates  # trap row must never appear
        if as_of_date >= date(2024, 4, 10):
            assert date(2024, 4, 10) in seen_filed_dates
        else:
            assert date(2024, 4, 10) not in seen_filed_dates


def test_insider_transactions_gated_on_filed_date_not_transaction_date():
    start, end = date(2024, 4, 1), date(2024, 4, 20)
    bars = _bars("AAPL", pd.date_range(start, end, freq="D").date.tolist(), [100.0] * 20)

    visible_row = {
        "cik": "0000320193",
        "ticker": "AAPL",
        "insider_name": "Jane Q. Doe",
        "insider_title": "CFO",
        "transaction_date": date(2024, 4, 5),
        "filed_date": date(2024, 4, 8),
        "transaction_code": "P",
        "shares": 1000.0,
        "price": 150.0,
        "shares_owned_after": 5000.0,
    }
    # The trap: an old transaction_date (well before `start`) paired with
    # a filed_date AFTER the whole backtest window.
    trap_row = {
        "cik": "0000320193",
        "ticker": "AAPL",
        "insider_name": "Old Insider",
        "insider_title": "Director",
        "transaction_date": date(2023, 12, 1),
        "filed_date": date(2024, 4, 22),
        "transaction_code": "P",
        "shares": 2000.0,
        "price": 140.0,
        "shares_owned_after": 9000.0,
    }
    transactions = pd.DataFrame([visible_row, trap_row])

    strategy = _RecordingStrategy()
    run_backtest(strategy, bars, _EMPTY_HOLDINGS, transactions, start, end)

    for as_of_date, fundamental_data in strategy.fundamental_data_calls.items():
        seen_filed_dates = set(pd.to_datetime(fundamental_data.insider_transactions["filed_date"]).dt.date)
        assert date(2024, 4, 22) not in seen_filed_dates  # trap row must never appear
        if as_of_date >= date(2024, 4, 8):
            assert date(2024, 4, 8) in seen_filed_dates
        else:
            assert date(2024, 4, 8) not in seen_filed_dates
