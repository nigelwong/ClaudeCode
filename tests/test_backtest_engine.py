from datetime import date

import pandas as pd
import pytest

from tradesignals.backtest.costs import TransactionCosts
from tradesignals.backtest.engine import run_backtest
from tradesignals.signals.base import FundamentalData, ScoreComponents, Strategy

_EMPTY_HOLDINGS = pd.DataFrame(columns=["ticker", "filed_date"])
_EMPTY_TRANSACTIONS = pd.DataFrame(columns=["ticker", "filed_date"])

_ZERO_COSTS = TransactionCosts(slippage_bps=0.0, commission_per_fill=0.0)


class _ScriptedStrategy(Strategy):
    """Returns a fixed, hand-authored score per ticker per as_of_date so
    backtest trade sequences are fully deterministic and traceable."""

    name = "scripted"
    required_lookback_days = 0

    def __init__(self, schedule: dict[date, dict[str, float]]):
        self.schedule = schedule

    def score(
        self, as_of_date: date, market_data: pd.DataFrame, fundamental_data: FundamentalData
    ) -> dict[str, ScoreComponents]:
        day_scores = self.schedule.get(as_of_date, {})
        return {ticker: ScoreComponents(score=score) for ticker, score in day_scores.items()}


def _staircase_bars(ticker: str, start: date, opens: list[float], closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(opens), freq="D").date
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": opens,
            "high": [max(o, c) for o, c in zip(opens, closes)],
            "low": [min(o, c) for o, c in zip(opens, closes)],
            "close": closes,
            "volume": 1_000_000,
        }
    )


def test_long_trade_zero_costs_hand_traced():
    days = [date(2024, 1, d) for d in range(1, 6)]
    opens = [100.0, 102.0, 104.0, 106.0, 108.0]
    closes = [101.0, 103.0, 105.0, 107.0, 109.0]
    bars = _staircase_bars("TEST", days[0], opens, closes)

    schedule = {
        days[0]: {"TEST": 0.0},
        days[1]: {"TEST": 1.0},  # queues open, fills day3's open=104
        days[2]: {"TEST": 1.0},  # stays open
        days[3]: {"TEST": 0.0},  # queues close, fills day5's open=108
    }
    strategy = _ScriptedStrategy(schedule)

    result = run_backtest(
        strategy, bars, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, days[0], days[-1], costs=_ZERO_COSTS
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "long"
    assert trade.entry_date == days[2]
    assert trade.entry_price == pytest.approx(104.0)
    assert trade.exit_date == days[4]
    assert trade.exit_price == pytest.approx(108.0)
    assert trade.pnl_pct == pytest.approx((108.0 - 104.0) / 104.0)
    assert trade.pnl == pytest.approx(10_000 * (108.0 - 104.0) / 104.0)

    position_value = 10_000.0
    expected_equity = {
        days[0]: 100_000.0,
        days[1]: 100_000.0,
        days[2]: 100_000.0 + position_value * (105.0 - 104.0) / 104.0,
        days[3]: 100_000.0 + position_value * (107.0 - 104.0) / 104.0,
        days[4]: 100_000.0 + trade.pnl,
    }
    for day, expected in expected_equity.items():
        assert result.equity_curve[day] == pytest.approx(expected)


def test_long_trade_with_nonzero_costs_uses_costs_object():
    days = [date(2024, 1, d) for d in range(1, 6)]
    opens = [100.0, 102.0, 104.0, 106.0, 108.0]
    closes = [101.0, 103.0, 105.0, 107.0, 109.0]
    bars = _staircase_bars("TEST", days[0], opens, closes)

    schedule = {
        days[0]: {"TEST": 0.0},
        days[1]: {"TEST": 1.0},
        days[2]: {"TEST": 1.0},
        days[3]: {"TEST": 0.0},
    }
    strategy = _ScriptedStrategy(schedule)
    costs = TransactionCosts(slippage_bps=5.0, commission_per_fill=1.0)

    result = run_backtest(strategy, bars, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, days[0], days[-1], costs=costs)

    assert len(result.trades) == 1
    trade = result.trades[0]
    expected_entry = costs.apply_entry(104.0)
    expected_exit = costs.apply_exit(108.0)
    expected_pnl_pct = (expected_exit - expected_entry) / expected_entry
    expected_pnl = expected_pnl_pct * 10_000 - 2 * costs.commission_per_fill

    assert trade.entry_price == pytest.approx(expected_entry)
    assert trade.exit_price == pytest.approx(expected_exit)
    assert trade.pnl_pct == pytest.approx(expected_pnl_pct)
    assert trade.pnl == pytest.approx(expected_pnl)


def test_short_trade_zero_costs_hand_traced():
    days = [date(2024, 1, d) for d in range(1, 6)]
    opens = [110.0, 108.0, 106.0, 104.0, 102.0]
    closes = [109.0, 107.0, 105.0, 103.0, 101.0]
    bars = _staircase_bars("SHORTME", days[0], opens, closes)

    schedule = {
        days[0]: {"SHORTME": 0.0},
        days[1]: {"SHORTME": -1.0},  # queues short open, fills day3's open=106
        days[2]: {"SHORTME": -1.0},  # stays open
        days[3]: {"SHORTME": 0.0},  # queues close, fills day5's open=102
    }
    strategy = _ScriptedStrategy(schedule)

    result = run_backtest(
        strategy, bars, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, days[0], days[-1], costs=_ZERO_COSTS
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "short"
    assert trade.entry_date == days[2]
    assert trade.entry_price == pytest.approx(106.0)
    assert trade.exit_date == days[4]
    assert trade.exit_price == pytest.approx(102.0)

    expected_pnl_pct = -1 * (trade.exit_price - trade.entry_price) / trade.entry_price
    expected_pnl = expected_pnl_pct * 10_000
    assert trade.pnl_pct == pytest.approx(expected_pnl_pct)
    assert trade.pnl == pytest.approx(expected_pnl)


def test_open_position_force_closed_at_end_of_window():
    days = [date(2024, 1, d) for d in range(1, 5)]
    opens = [100.0, 102.0, 104.0, 106.0]
    closes = [101.0, 103.0, 105.0, 107.0]
    bars = _staircase_bars("HOLD", days[0], opens, closes)

    schedule = {
        days[0]: {"HOLD": 0.0},
        days[1]: {"HOLD": 1.0},  # queues open, fills day3's open=104
        # no close signal before the window ends
    }
    strategy = _ScriptedStrategy(schedule)

    result = run_backtest(
        strategy, bars, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, days[0], days[-1], costs=_ZERO_COSTS
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_date == days[2]
    assert trade.entry_price == pytest.approx(104.0)
    # Force-closed at the last trading day's close (107.0), not its open.
    assert trade.exit_date == days[3]
    assert trade.exit_price == pytest.approx(107.0)
    assert trade.pnl_pct == pytest.approx((107.0 - 104.0) / 104.0)


def test_pending_order_retried_next_day_if_ticker_has_no_bar_today():
    days = [date(2024, 1, d) for d in range(1, 5)]
    # "OTHER" has a bar every day so day2 is still a trading day even
    # though "GAP" has no bar then -- the open order queued for GAP on
    # day1 must stay pending through day2 and fill on day3's open.
    gap_bars = pd.concat(
        [
            _staircase_bars("GAP", days[0], [100.0], [101.0]),
            _staircase_bars("GAP", days[2], [104.0, 106.0], [105.0, 107.0]),
        ],
        ignore_index=True,
    )
    other_bars = _staircase_bars("OTHER", days[0], [50.0] * 4, [50.0] * 4)
    bars = pd.concat([gap_bars, other_bars], ignore_index=True)

    schedule = {
        days[0]: {"GAP": 1.0},  # queues open; GAP has no bar on day2
    }
    strategy = _ScriptedStrategy(schedule)

    result = run_backtest(
        strategy, bars, _EMPTY_HOLDINGS, _EMPTY_TRANSACTIONS, days[0], days[-1], costs=_ZERO_COSTS
    )

    # The position should have opened on day3 (the next day GAP has a
    # bar), not day2, and remains open (no close signal) so it
    # force-closes at the window's last bar (day4, close=107.0).
    gap_trades = [t for t in result.trades if t.ticker == "GAP"]
    assert len(gap_trades) == 1
    trade = gap_trades[0]
    assert trade.entry_date == days[2]
    assert trade.entry_price == pytest.approx(104.0)
    assert trade.exit_date == days[3]
    assert trade.exit_price == pytest.approx(107.0)
