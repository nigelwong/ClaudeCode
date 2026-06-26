from datetime import date

import pandas as pd
import pytest

from tradesignals.backtest.costs import TransactionCosts
from tradesignals.backtest.engine import Trade
from tradesignals.backtest.regime_engine import run_regime_backtest

_NO_COST = TransactionCosts(slippage_bps=0.0, commission_per_fill=0.0)

# benchmark/bonds/gold tickers are never given any bars, so trend.py /
# risk_tilt.py / sector_rank.py all fall back to their documented
# "insufficient history" defaults (NEUTRAL trend, NEUTRAL risk_tilt,
# all-NEUTRAL sector tiers) regardless of S1/S2 price action -- this
# keeps the regime call fixed at NEUTRAL throughout, so target weights
# are hand-traceable: risky_pct=0.7 split evenly 0.35/0.35 across S1/S2,
# safe_pct=0.3 to CASH (risk_tilt is NEUTRAL, not RISK_OFF).
_BENCHMARK, _BONDS, _GOLD = "SPY", "TLT", "GLD"
_EMPTY_MACRO = pd.DataFrame(columns=["date", "series_id", "value"])


def _bar(ticker: str, dt, open_: float, close: float) -> dict:
    return {"ticker": ticker, "date": dt, "open": open_, "close": close}


def test_basic_rebalance_and_pnl_trace():
    dates = pd.bdate_range("2024-01-02", periods=3)  # day0 decide, day1 fill, day2 force-close
    bars = pd.DataFrame(
        [
            _bar("S1", dates[0], 50, 50),
            _bar("S1", dates[1], 50, 55),
            _bar("S1", dates[2], 60, 60),
            _bar("S2", dates[0], 50, 50),
            _bar("S2", dates[1], 50, 45),
            _bar("S2", dates[2], 45, 45),
        ]
    )

    result = run_regime_backtest(
        bars=bars,
        macro_series=_EMPTY_MACRO,
        benchmark_ticker=_BENCHMARK,
        breadth_tickers=[],
        sector_tickers=["S1", "S2"],
        bonds_ticker=_BONDS,
        gold_ticker=_GOLD,
        start=dates[0].date(),
        end=dates[2].date(),
        rebalance_every_n_days=3,  # only day0 is a decision day
        initial_capital=100_000.0,
        costs=_NO_COST,
    )

    assert len(result.rebalances) == 1
    rebalance = result.rebalances[0]
    assert rebalance.date == dates[0].date()
    assert rebalance.target_weights == pytest.approx({"CASH": 0.3, "S1": 0.35, "S2": 0.35})

    trades_by_ticker = {t.ticker: t for t in result.trades}
    assert set(trades_by_ticker) == {"S1", "S2"}

    s1 = trades_by_ticker["S1"]
    assert s1 == Trade(
        ticker="S1",
        entry_date=dates[1].date(),
        side="long",
        entry_price=50.0,
        exit_date=dates[2].date(),
        exit_price=60.0,
        pnl=pytest.approx(7000.0),
        pnl_pct=pytest.approx(0.2),
    )

    s2 = trades_by_ticker["S2"]
    assert s2 == Trade(
        ticker="S2",
        entry_date=dates[1].date(),
        side="long",
        entry_price=50.0,
        exit_date=dates[2].date(),
        exit_price=45.0,
        pnl=pytest.approx(-3500.0),
        pnl_pct=pytest.approx(-0.1),
    )

    assert result.equity_curve[dates[0].date()] == pytest.approx(100_000.0)
    assert result.equity_curve[dates[1].date()] == pytest.approx(100_000.0)
    assert result.equity_curve[dates[2].date()] == pytest.approx(103_500.0)


def test_drift_below_threshold_skips_rebalance():
    dates = pd.bdate_range("2024-01-02", periods=6)
    rows = []
    for ticker in ("S1", "S2"):
        for dt in dates:
            rows.append(_bar(ticker, dt, 50, 50))  # flat the whole window
    bars = pd.DataFrame(rows)

    result = run_regime_backtest(
        bars=bars,
        macro_series=_EMPTY_MACRO,
        benchmark_ticker=_BENCHMARK,
        breadth_tickers=[],
        sector_tickers=["S1", "S2"],
        bonds_ticker=_BONDS,
        gold_ticker=_GOLD,
        start=dates[0].date(),
        end=dates[5].date(),
        rebalance_every_n_days=3,  # decision days: index 0 and 3
        initial_capital=100_000.0,
        costs=_NO_COST,
    )

    assert len(result.rebalances) == 2
    assert result.rebalances[0].target_weights == result.rebalances[1].target_weights

    # flat prices mean weight never drifts off target at the 2nd decision
    # day, so the dead-band must skip re-trading -- exactly one continuous
    # open/close cycle per ticker, not a spurious close+reopen at day 3.
    assert len(result.trades) == 2
    for trade in result.trades:
        assert trade.entry_date == dates[1].date()
        assert trade.exit_date == dates[5].date()
        assert trade.pnl == pytest.approx(0.0)


def test_position_with_no_bar_on_final_day_keeps_value_in_equity():
    dates = pd.bdate_range("2024-01-02", periods=3)
    bars = pd.DataFrame(
        [
            _bar("S1", dates[0], 50, 50),
            _bar("S1", dates[1], 50, 55),
            _bar("S1", dates[2], 60, 60),
            _bar("S2", dates[0], 50, 50),
            _bar("S2", dates[1], 50, 45),
            # no S2 bar on dates[2] -- it can't be force-closed
        ]
    )

    result = run_regime_backtest(
        bars=bars,
        macro_series=_EMPTY_MACRO,
        benchmark_ticker=_BENCHMARK,
        breadth_tickers=[],
        sector_tickers=["S1", "S2"],
        bonds_ticker=_BONDS,
        gold_ticker=_GOLD,
        start=dates[0].date(),
        end=dates[2].date(),
        rebalance_every_n_days=3,
        initial_capital=100_000.0,
        costs=_NO_COST,
    )

    # only S1 could be closed; S2 has no bar on the final day and stays open
    assert [t.ticker for t in result.trades] == ["S1"]

    # cash after closing S1 (30000 + 35000 + 7000 = 72000) plus S2's
    # frozen entry-time value (35000) -- must not silently drop S2.
    assert result.equity_curve[dates[2].date()] == pytest.approx(107_000.0)
