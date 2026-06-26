from dataclasses import dataclass
from datetime import date

import pandas as pd

from tradesignals.backtest.costs import TransactionCosts
from tradesignals.signals.base import FundamentalData, Strategy


@dataclass
class Trade:
    ticker: str
    entry_date: date
    side: str  # "long" or "short"
    entry_price: float
    exit_date: date | None = None
    exit_price: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None


@dataclass
class BacktestResult:
    equity_curve: pd.Series  # indexed by date
    trades: list[Trade]


def _direction(side: str) -> int:
    return 1 if side == "long" else -1


def run_backtest(
    strategy: Strategy,
    bars: pd.DataFrame,
    institutional_holdings: pd.DataFrame,
    insider_transactions: pd.DataFrame,
    start: date,
    end: date,
    entry_threshold: float = 0.5,
    exit_threshold: float = 0.0,
    initial_capital: float = 100_000.0,
    position_size_pct: float = 0.1,
    costs: TransactionCosts | None = None,
) -> BacktestResult:
    """Walks trading days in [start, end].

    `bars`, `institutional_holdings`, and `insider_transactions` are
    expected to be the FULL available history (not pre-trimmed to
    [start, end]) -- the engine itself filters every input to
    `<= current_date` on each iteration, which is the no-lookahead
    invariant. For the SEC tables this means filtering on `filed_date`
    (when a filing became public), never `report_period`/
    `transaction_date` (the underlying fact date, which can be known to
    the engine's caller well before it was actually public).

    Orders decided from day t's (lookahead-safe) score are filled at day
    t+1's open, not day t's close, since trading at the exact bar that
    triggered the signal is not a realistic fill assumption.
    """
    costs = costs or TransactionCosts()

    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    holdings = institutional_holdings.copy()
    holdings["filed_date"] = pd.to_datetime(holdings["filed_date"])
    transactions = insider_transactions.copy()
    transactions["filed_date"] = pd.to_datetime(transactions["filed_date"])

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    trading_days = sorted(bars.loc[(bars["date"] >= start_ts) & (bars["date"] <= end_ts), "date"].unique())

    open_positions: dict[str, Trade] = {}
    closed_trades: list[Trade] = []
    cash = initial_capital
    equity_by_date: dict[date, float] = {}
    pending_orders: list[dict] = []
    position_value = initial_capital * position_size_pct

    def _realize_close(ticker: str, trade: Trade, exit_price: float, exit_date: pd.Timestamp) -> None:
        nonlocal cash
        trade.exit_date = exit_date.date()
        trade.exit_price = exit_price
        trade.pnl_pct = _direction(trade.side) * (exit_price - trade.entry_price) / trade.entry_price
        trade.pnl = trade.pnl_pct * position_value - 2 * costs.commission_per_fill
        cash += trade.pnl
        closed_trades.append(trade)

    for current_ts in trading_days:
        bars_to_date = bars[bars["date"] <= current_ts]
        todays_bars = bars[bars["date"] == current_ts].set_index("ticker")

        still_pending = []
        for order in pending_orders:
            ticker = order["ticker"]
            if ticker not in todays_bars.index:
                still_pending.append(order)  # ticker didn't trade today; retry next day
                continue
            fill_price = float(todays_bars.loc[ticker, "open"])
            if order["action"] == "open" and ticker not in open_positions:
                side = order["side"]
                entry_price = costs.apply_entry(fill_price) if side == "long" else costs.apply_exit(fill_price)
                open_positions[ticker] = Trade(
                    ticker=ticker, entry_date=current_ts.date(), side=side, entry_price=entry_price
                )
            elif order["action"] == "close" and ticker in open_positions:
                trade = open_positions.pop(ticker)
                exit_price = costs.apply_exit(fill_price) if trade.side == "long" else costs.apply_entry(fill_price)
                _realize_close(ticker, trade, exit_price, current_ts)
        pending_orders = still_pending

        equity = cash
        for ticker, trade in open_positions.items():
            if ticker in todays_bars.index:
                close_price = float(todays_bars.loc[ticker, "close"])
                unrealized_pct = _direction(trade.side) * (close_price - trade.entry_price) / trade.entry_price
                equity += position_value * unrealized_pct
        equity_by_date[current_ts.date()] = equity

        fundamental_data = FundamentalData(
            institutional_holdings=holdings[holdings["filed_date"] <= current_ts],
            insider_transactions=transactions[transactions["filed_date"] <= current_ts],
        )
        scores = strategy.score(current_ts.date(), bars_to_date, fundamental_data)
        for ticker, components in scores.items():
            has_position = ticker in open_positions
            if not has_position and abs(components.score) >= entry_threshold:
                side = "long" if components.score > 0 else "short"
                pending_orders.append({"ticker": ticker, "action": "open", "side": side})
            elif has_position and abs(components.score) <= exit_threshold:
                pending_orders.append({"ticker": ticker, "action": "close"})

    if trading_days:
        last_ts = trading_days[-1]
        last_bars = bars[bars["date"] == last_ts].set_index("ticker")
        for ticker, trade in list(open_positions.items()):
            if ticker not in last_bars.index:
                continue
            _realize_close(ticker, trade, float(last_bars.loc[ticker, "close"]), last_ts)

    equity_curve = pd.Series(equity_by_date).sort_index()
    return BacktestResult(equity_curve=equity_curve, trades=closed_trades)
