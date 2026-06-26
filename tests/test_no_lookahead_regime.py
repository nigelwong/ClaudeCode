import pandas as pd

from tradesignals.backtest.costs import TransactionCosts
from tradesignals.backtest.regime_engine import run_regime_backtest

_NO_COST = TransactionCosts(slippage_bps=0.0, commission_per_fill=0.0)
_BENCHMARK, _BONDS, _GOLD = "SPY", "TLT", "GLD"


def _bar(ticker: str, dt, open_: float, close: float) -> dict:
    return {"ticker": ticker, "date": dt, "open": open_, "close": close}


def _macro_row(series_id: str, dt, value: float) -> dict:
    return {"date": dt, "series_id": series_id, "value": value}


def _run(bars: pd.DataFrame, macro: pd.DataFrame, dates) -> "object":
    return run_regime_backtest(
        bars=bars,
        macro_series=macro,
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


def _base_bars(dates) -> pd.DataFrame:
    return pd.DataFrame(
        [
            _bar("S1", dates[0], 50, 50),
            _bar("S1", dates[1], 50, 55),
            _bar("S1", dates[2], 60, 60),
            _bar("S2", dates[0], 50, 50),
            _bar("S2", dates[1], 50, 45),
            _bar("S2", dates[2], 45, 45),
        ]
    )


def _base_macro(dates) -> pd.DataFrame:
    rows = []
    for dt in dates:
        rows.append(_macro_row("VIXCLS", dt, 15.0))
        rows.append(_macro_row("T10Y2Y", dt, 1.0))
        rows.append(_macro_row("BAMLH0A0HYM2", dt, 3.0))
    return pd.DataFrame(rows)


def test_future_bars_do_not_affect_backtest_output():
    dates = pd.bdate_range("2024-01-02", periods=3)
    macro = _base_macro(dates)

    honest = _run(_base_bars(dates), macro, dates)

    future_date = dates[2] + pd.Timedelta(days=10)
    trapped_bars = pd.concat(
        [
            _base_bars(dates),
            pd.DataFrame([_bar("S1", future_date, 999_999.0, 999_999.0)]),
        ],
        ignore_index=True,
    )
    trapped = _run(trapped_bars, macro, dates)

    pd.testing.assert_series_equal(honest.equity_curve, trapped.equity_curve)
    assert honest.trades == trapped.trades
    assert honest.rebalances == trapped.rebalances


def test_future_macro_rows_do_not_affect_backtest_output():
    dates = pd.bdate_range("2024-01-02", periods=3)
    bars = _base_bars(dates)

    honest = _run(bars, _base_macro(dates), dates)

    future_date = dates[2] + pd.Timedelta(days=10)
    trapped_macro = pd.concat(
        [
            _base_macro(dates),
            pd.DataFrame([_macro_row("VIXCLS", future_date, 999.0)]),
        ],
        ignore_index=True,
    )
    trapped = _run(bars, trapped_macro, dates)

    pd.testing.assert_series_equal(honest.equity_curve, trapped.equity_curve)
    assert honest.trades == trapped.trades
    assert honest.rebalances == trapped.rebalances
