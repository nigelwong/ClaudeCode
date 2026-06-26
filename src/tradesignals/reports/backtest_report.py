from datetime import date

from tradesignals.backtest.engine import BacktestResult
from tradesignals.backtest.sweep import SweepCandidate


def render_backtest_markdown(
    strategy_name: str,
    start: date,
    end: date,
    result: BacktestResult,
    metrics: dict[str, float],
    benchmark: dict[str, float] | None = None,
) -> str:
    bench_return = f"{benchmark['benchmark_total_return']:.2%}" if benchmark else "-"
    bench_sharpe = f"{benchmark['benchmark_sharpe']:.2f}" if benchmark else "-"

    lines = [
        f"# Backtest: {strategy_name} ({start.isoformat()} to {end.isoformat()})",
        "",
        "## Metrics",
        "| Metric | Strategy | Benchmark |",
        "|--------|----------|-----------|",
        f"| Total return | {metrics['total_return']:.2%} | {bench_return} |",
        f"| Annualized return | {metrics['annualized_return']:.2%} | - |",
        f"| Sharpe | {metrics['sharpe']:.2f} | {bench_sharpe} |",
        f"| Win rate | {metrics['win_rate']:.2%} | - |",
        f"| Max drawdown | {metrics['max_drawdown']:.2%} | - |",
        "",
        f"## Trades ({len(result.trades)})",
    ]
    if result.trades:
        lines.append("| Ticker | Side | Entry | Exit | PnL | PnL % |")
        lines.append("|--------|------|-------|------|-----|-------|")
        for t in result.trades:
            pnl = f"{t.pnl:.2f}" if t.pnl is not None else "-"
            pnl_pct = f"{t.pnl_pct:.2%}" if t.pnl_pct is not None else "-"
            lines.append(f"| {t.ticker} | {t.side} | {t.entry_date} | {t.exit_date or '-'} | {pnl} | {pnl_pct} |")
    else:
        lines.append("No closed trades.")
    return "\n".join(lines) + "\n"


def render_sweep_markdown(strategy_name: str, candidates: list[SweepCandidate], rank_metric: str = "sharpe") -> str:
    lines = [
        f"# Sweep: {strategy_name} (ranked by out-of-sample {rank_metric})",
        "",
        f"| Params | Train {rank_metric} | Test {rank_metric} |",
        "|--------|--------------|-------------|",
    ]
    for c in candidates:
        lines.append(f"| {c.params} | {c.train_metrics[rank_metric]:.3f} | {c.test_metrics[rank_metric]:.3f} |")
    return "\n".join(lines) + "\n"
