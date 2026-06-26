from dataclasses import dataclass
from datetime import date

import pandas as pd

from tradesignals.backtest.costs import TransactionCosts
from tradesignals.backtest.engine import Trade
from tradesignals.regime.outlook import compute_outlook
from tradesignals.regime.risk_tilt import RiskTilt
from tradesignals.regime.sector_rank import SectorTier
from tradesignals.regime.trend import TrendRegime

CASH = "CASH"

DEFAULT_EQUITY_EXPOSURE_BY_REGIME: dict[TrendRegime, float] = {
    TrendRegime.BULL: 1.0,
    TrendRegime.NEUTRAL: 0.7,
    TrendRegime.CORRECTION_WATCH: 0.4,
    TrendRegime.BEAR: 0.15,
}

_TIER_MULTIPLIER: dict[SectorTier, float] = {
    SectorTier.OVERWEIGHT: 1.5,
    SectorTier.NEUTRAL: 1.0,
    SectorTier.UNDERWEIGHT: 0.5,
}

DEFAULT_REBALANCE_EVERY_N_DAYS = 5  # ~1 trading week
DEFAULT_REBALANCE_THRESHOLD_PCT = 0.01


@dataclass
class Rebalance:
    date: date
    overall_regime: TrendRegime
    risk_tilt: RiskTilt
    target_weights: dict[str, float]


@dataclass
class RegimeBacktestResult:
    equity_curve: pd.Series  # indexed by date
    trades: list[Trade]
    rebalances: list[Rebalance]


def _target_weights(
    overall_regime: TrendRegime,
    risk_tilt: RiskTilt,
    sector_tiers: dict[str, SectorTier],
    bonds_ticker: str,
    gold_ticker: str,
    equity_exposure_by_regime: dict[TrendRegime, float],
) -> dict[str, float]:
    """Two-level allocation. Top level: risky_pct is purely a function of
    overall_regime (trend-derived); safe_pct = 1 - risky_pct goes to cash,
    unless risk_tilt == RISK_OFF, in which case it splits 50/50 bonds/gold
    -- risk_tilt only ever redirects the safe bucket, never resizes the
    risky bucket, per risk_tilt.py's orthogonality contract. Within the
    risky bucket: equal-weight base across sectors x tier multiplier,
    renormalized to sum to risky_pct (the equal-weight base cancels out of
    the renormalization, so it reduces to multiplier-proportional split).
    """
    risky_pct = equity_exposure_by_regime[overall_regime]
    safe_pct = 1.0 - risky_pct

    weights: dict[str, float] = {}
    if risk_tilt == RiskTilt.RISK_OFF:
        weights[bonds_ticker] = safe_pct / 2
        weights[gold_ticker] = safe_pct / 2
    else:
        weights[CASH] = safe_pct

    if sector_tiers and risky_pct > 0:
        multipliers = {ticker: _TIER_MULTIPLIER[tier] for ticker, tier in sector_tiers.items()}
        total = sum(multipliers.values())
        for ticker, multiplier in multipliers.items():
            weights[ticker] = weights.get(ticker, 0.0) + risky_pct * multiplier / total

    return weights


def run_regime_backtest(
    bars: pd.DataFrame,
    macro_series: pd.DataFrame,
    benchmark_ticker: str,
    breadth_tickers: list[str],
    sector_tickers: list[str],
    bonds_ticker: str,
    gold_ticker: str,
    start: date,
    end: date,
    rebalance_every_n_days: int = DEFAULT_REBALANCE_EVERY_N_DAYS,
    equity_exposure_by_regime: dict[TrendRegime, float] | None = None,
    rebalance_threshold_pct: float = DEFAULT_REBALANCE_THRESHOLD_PCT,
    initial_capital: float = 100_000.0,
    costs: TransactionCosts | None = None,
) -> RegimeBacktestResult:
    """Walks trading days in [start, end], rebalancing a multi-asset
    portfolio (cash/bonds/gold + 11 sector ETFs) every
    `rebalance_every_n_days` trading days, instead of evaluating
    per-ticker entry/exit thresholds daily like engine.py's per-stock
    variant.

    `bars` and `macro_series` are expected to be the FULL available
    history (not pre-trimmed to [start, end]) -- every regime sub-signal
    is computed from data filtered to `<= current_date` on each
    rebalance, the same no-lookahead invariant as engine.py, extended to
    macro_series.

    Target weights decided from day t's data are filled at day t+1's
    open. A position is only re-traded (closed and reopened at its new
    target size) when its mark-to-market weight has drifted from target
    by at least `rebalance_threshold_pct` -- the dead-band that avoids
    churning on negligible drift.
    """
    costs = costs or TransactionCosts()
    equity_exposure_by_regime = equity_exposure_by_regime or DEFAULT_EQUITY_EXPOSURE_BY_REGIME

    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    macro = macro_series.copy()
    macro["date"] = pd.to_datetime(macro["date"])

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    trading_days = sorted(bars.loc[(bars["date"] >= start_ts) & (bars["date"] <= end_ts), "date"].unique())
    decision_days = set(trading_days[::rebalance_every_n_days])

    open_positions: dict[str, Trade] = {}
    position_value: dict[str, float] = {}
    closed_trades: list[Trade] = []
    rebalances: list[Rebalance] = []
    cash = initial_capital
    equity_by_date: dict[date, float] = {}
    pending_orders: list[dict] = []

    def _mark_values(todays_bars: pd.DataFrame) -> dict[str, float]:
        values = {}
        for ticker, trade in open_positions.items():
            if ticker in todays_bars.index:
                close_price = float(todays_bars.loc[ticker, "close"])
                values[ticker] = position_value[ticker] * close_price / trade.entry_price
            else:
                values[ticker] = position_value[ticker]
        return values

    def _close(ticker: str, fill_price: float, exit_date: pd.Timestamp) -> None:
        nonlocal cash
        trade = open_positions.pop(ticker)
        value = position_value.pop(ticker)
        exit_price = costs.apply_exit(fill_price)
        trade.exit_date = exit_date.date()
        trade.exit_price = exit_price
        trade.pnl_pct = (exit_price - trade.entry_price) / trade.entry_price
        trade.pnl = trade.pnl_pct * value - 2 * costs.commission_per_fill
        cash += value + trade.pnl
        closed_trades.append(trade)

    def _open(ticker: str, fill_price: float, entry_date: pd.Timestamp, value: float) -> None:
        nonlocal cash
        entry_price = costs.apply_entry(fill_price)
        open_positions[ticker] = Trade(ticker=ticker, entry_date=entry_date.date(), side="long", entry_price=entry_price)
        position_value[ticker] = value
        cash -= value

    for current_ts in trading_days:
        todays_bars = bars[bars["date"] == current_ts].set_index("ticker")

        still_pending = []
        for order in pending_orders:
            ticker = order["ticker"]
            if ticker not in todays_bars.index:
                still_pending.append(order)  # ticker didn't trade today; retry next day
                continue
            fill_price = float(todays_bars.loc[ticker, "open"])
            if order["action"] == "close":
                _close(ticker, fill_price, current_ts)
            elif order["action"] == "open":
                _open(ticker, fill_price, current_ts, order["value"])
        pending_orders = still_pending

        mark_values = _mark_values(todays_bars)
        equity = cash + sum(mark_values.values())
        equity_by_date[current_ts.date()] = equity

        if current_ts in decision_days:
            bars_to_date = bars[bars["date"] <= current_ts]
            macro_to_date = macro[macro["date"] <= current_ts]

            outlook = compute_outlook(
                bars_to_date,
                macro_to_date,
                benchmark_ticker,
                breadth_tickers,
                sector_tickers,
                bonds_ticker,
                gold_ticker,
                current_ts.date(),
            )
            target_weights = _target_weights(
                outlook.overall_regime,
                outlook.risk_tilt,
                outlook.sector_tiers,
                bonds_ticker,
                gold_ticker,
                equity_exposure_by_regime,
            )
            rebalances.append(
                Rebalance(
                    date=current_ts.date(),
                    overall_regime=outlook.overall_regime,
                    risk_tilt=outlook.risk_tilt,
                    target_weights=target_weights,
                )
            )

            tradable_tickers = (set(target_weights) - {CASH}) | set(open_positions)
            for ticker in tradable_tickers:
                target = target_weights.get(ticker, 0.0)
                current_weight = mark_values.get(ticker, 0.0) / equity if equity else 0.0
                if abs(target - current_weight) < rebalance_threshold_pct:
                    continue
                if ticker in open_positions:
                    pending_orders.append({"ticker": ticker, "action": "close"})
                if target > 0:
                    pending_orders.append({"ticker": ticker, "action": "open", "value": target * equity})

    if trading_days:
        last_ts = trading_days[-1]
        last_bars = bars[bars["date"] == last_ts].set_index("ticker")
        for ticker in list(open_positions):
            if ticker in last_bars.index:
                _close(ticker, float(last_bars.loc[ticker, "close"]), last_ts)
        remaining_values = _mark_values(last_bars)
        equity_by_date[last_ts.date()] = cash + sum(remaining_values.values())

    equity_curve = pd.Series(equity_by_date).sort_index()
    return RegimeBacktestResult(equity_curve=equity_curve, trades=closed_trades, rebalances=rebalances)
