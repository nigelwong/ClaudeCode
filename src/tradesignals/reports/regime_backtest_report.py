from datetime import date

from tradesignals.backtest.regime_engine import RegimeBacktestResult


def render_regime_backtest_markdown(
    start: date,
    end: date,
    result: RegimeBacktestResult,
    metrics: dict[str, float],
    benchmark: dict[str, float] | None = None,
) -> str:
    bench_return = f"{benchmark['benchmark_total_return']:.2%}" if benchmark else "-"
    bench_sharpe = f"{benchmark['benchmark_sharpe']:.2f}" if benchmark else "-"

    lines = [
        f"# Regime Backtest ({start.isoformat()} to {end.isoformat()})",
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
        f"## Rebalances ({len(result.rebalances)})",
    ]
    if result.rebalances:
        lines.append("| Date | Overall Regime | Risk Tilt | Target Weights |")
        lines.append("|------|-----------------|-----------|-----------------|")
        for r in result.rebalances:
            weights = ", ".join(f"{ticker}: {weight:.2%}" for ticker, weight in r.target_weights.items())
            lines.append(f"| {r.date} | {r.overall_regime.value} | {r.risk_tilt.value} | {weights} |")
    else:
        lines.append("No rebalances.")

    lines.append("")
    lines.append(f"## Trades ({len(result.trades)})")
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
