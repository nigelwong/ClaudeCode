import pandas as pd

from tradesignals.backtest.metrics import sharpe_ratio, total_return


def benchmark_metrics(benchmark_bars: pd.DataFrame) -> dict:
    """benchmark_bars: columns date, close for a single ticker (e.g. SPY),
    already filtered to the backtest's date range. Computes simple
    buy-and-hold metrics so every backtest report can show strategy vs.
    benchmark side by side."""
    equity_curve = benchmark_bars.sort_values("date")["close"].reset_index(drop=True)
    daily_returns = equity_curve.pct_change().dropna()
    return {
        "benchmark_total_return": total_return(equity_curve),
        "benchmark_sharpe": sharpe_ratio(daily_returns),
    }
