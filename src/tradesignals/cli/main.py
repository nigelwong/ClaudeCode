from datetime import date
from pathlib import Path

import pandas as pd
import typer
import yaml

from tradesignals.backtest.benchmark import benchmark_metrics
from tradesignals.backtest.costs import TransactionCosts
from tradesignals.backtest.engine import run_backtest
from tradesignals.backtest.metrics import compute_metrics
from tradesignals.backtest.sweep import sweep as run_sweep
from tradesignals.config import REPO_ROOT, get_settings, get_watchlist
from tradesignals.data.alpaca_client import AlpacaBarClient
from tradesignals.data.bar_cache import get_bars_cached, trailing_window
from tradesignals.data.edgar_client import EdgarClient
from tradesignals.data.form4 import fetch_insider_transactions
from tradesignals.data.form13f import fetch_institutional_holdings
from tradesignals.data.fred_client import MACRO_SERIES, FredClient
from tradesignals.data.macro_cache import get_macro_series_cached
from tradesignals.db import repository
from tradesignals.db.connection import get_connection
from tradesignals.reports.backtest_report import render_backtest_markdown, render_sweep_markdown
from tradesignals.reports.daily_report import write_report
from tradesignals.signals.base import FundamentalData
from tradesignals.signals.composite import generate_composite_signals
from tradesignals.signals.registry import build_strategy

app = typer.Typer()

_CUSIP_MAP_PATH = REPO_ROOT / "src" / "tradesignals" / "data" / "cusip_map.yaml"

_HOLDING_COLUMNS = ["cik", "filer_name", "cusip", "ticker", "report_period", "filed_date", "shares", "value_usd"]
_TRANSACTION_COLUMNS = [
    "cik", "ticker", "insider_name", "insider_title", "transaction_date",
    "filed_date", "transaction_code", "shares", "price", "shares_owned_after",
]


def _load_cusip_to_ticker() -> dict[str, str]:
    with open(_CUSIP_MAP_PATH) as f:
        ticker_to_cusip = yaml.safe_load(f)
    return {cusip: ticker for ticker, cusip in ticker_to_cusip.items()}


def _parse_value(raw: str) -> int | float | str:
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_params(params: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for item in params:
        key, _, value = item.partition("=")
        parsed[key] = _parse_value(value)
    return parsed


def _parse_param_grid(params: list[str]) -> dict[str, list[object]]:
    grid: dict[str, list[object]] = {}
    for item in params:
        key, _, values = item.partition("=")
        grid[key] = [_parse_value(v) for v in values.split(",")]
    return grid


@app.command("backfill-data")
def backfill_data(
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(None, help="YYYY-MM-DD, defaults to today"),
) -> None:
    """One-off historical backfill of bars + SEC filings + FRED macro series
    into the local SQLite cache."""
    settings = get_settings()
    watchlist = get_watchlist()
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end) if end else date.today()
    tickers = [*watchlist.tickers, watchlist.benchmark, *watchlist.cross_asset.tickers]

    bar_client = AlpacaBarClient(settings)
    edgar_client = EdgarClient(settings)
    cusip_to_ticker = _load_cusip_to_ticker()

    with get_connection(settings.db_path) as conn:
        typer.echo(f"Fetching bars for {len(tickers)} tickers...")
        get_bars_cached(conn, bar_client, tickers, start_date, end_date)

        typer.echo("Fetching insider transactions (Form 4)...")
        for ticker in watchlist.tickers:
            transactions = fetch_insider_transactions(edgar_client, ticker)
            rows = [t.model_dump(mode="json") for t in transactions]
            repository.upsert_insider_transactions(conn, rows)

        typer.echo("Fetching institutional holdings (13F)...")
        holdings = fetch_institutional_holdings(edgar_client, cusip_to_ticker)
        repository.upsert_institutional_holdings(conn, [h.model_dump(mode="json") for h in holdings])

        typer.echo("Fetching FRED macro series (VIX, yield curve, credit spread)...")
        fred_client = FredClient(settings)
        for series_id in MACRO_SERIES.values():
            get_macro_series_cached(conn, fred_client, series_id, start_date, end_date)

    typer.echo("Backfill complete.")


@app.command()
def backtest(
    strategy: str = typer.Option(..., help="Registered strategy name, e.g. ma_crossover"),
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(..., help="YYYY-MM-DD"),
    param: list[str] = typer.Option([], "--param", help="key=value, repeatable"),
    entry_threshold: float = 0.5,
    exit_threshold: float = 0.0,
    slippage_bps: float = 5.0,
    commission_per_fill: float = 0.0,
    output_dir: Path = typer.Option(REPO_ROOT / "reports", "--output-dir"),
) -> None:
    settings = get_settings()
    watchlist = get_watchlist()
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    strategy_obj = build_strategy(strategy, **_parse_params(param))
    costs = TransactionCosts(slippage_bps=slippage_bps, commission_per_fill=commission_per_fill)

    with get_connection(settings.db_path) as conn:
        bars = repository.get_bars(conn, watchlist.tickers)
        holdings = repository.get_institutional_holdings(conn, end_date, watchlist.tickers)
        transactions = repository.get_insider_transactions(conn, end_date, watchlist.tickers)
        benchmark_bars = repository.get_bars(conn, [watchlist.benchmark], start_date, end_date)

    if bars.empty:
        typer.echo("No cached bars found -- run `tradesignals backfill-data` first.", err=True)
        raise typer.Exit(1)

    result = run_backtest(
        strategy_obj, bars, holdings, transactions, start_date, end_date,
        entry_threshold=entry_threshold, exit_threshold=exit_threshold, costs=costs,
    )
    metrics = compute_metrics(result.equity_curve, [t.pnl for t in result.trades])
    bench = benchmark_metrics(benchmark_bars) if not benchmark_bars.empty else None

    report_md = render_backtest_markdown(strategy, start_date, end_date, result, metrics, bench)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"backtest-{strategy}-{start_date}-{end_date}.md"
    report_path.write_text(report_md)
    typer.echo(report_md)
    typer.echo(f"Report written to {report_path}")


@app.command()
def sweep(
    strategy: str = typer.Option(..., help="Registered strategy name, e.g. momentum"),
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(..., help="YYYY-MM-DD"),
    param: list[str] = typer.Option(..., "--param", help="key=v1,v2,v3, repeatable"),
    mode: str = typer.Option("grid", help="grid or random"),
    n_samples: int = 20,
    split: str = typer.Option("train_test", help="train_test or walk_forward"),
    train_window_days: int = 365,
    test_window_days: int = 90,
    entry_threshold: float = 0.5,
    exit_threshold: float = 0.0,
    rank_metric: str = "sharpe",
    output_dir: Path = typer.Option(REPO_ROOT / "reports", "--output-dir"),
) -> None:
    """Always reports in-sample vs. out-of-sample (or walk-forward) results
    and ranks only on the out-of-sample metric -- see CLAUDE.md invariant #4."""
    settings = get_settings()
    watchlist = get_watchlist()
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    param_grid = _parse_param_grid(param)

    with get_connection(settings.db_path) as conn:
        bars = repository.get_bars(conn, watchlist.tickers)
        holdings = repository.get_institutional_holdings(conn, end_date, watchlist.tickers)
        transactions = repository.get_insider_transactions(conn, end_date, watchlist.tickers)

    if bars.empty:
        typer.echo("No cached bars found -- run `tradesignals backfill-data` first.", err=True)
        raise typer.Exit(1)

    candidates = run_sweep(
        strategy, param_grid, bars, holdings, transactions, start_date, end_date,
        mode=mode, n_samples=n_samples, split=split,
        train_window_days=train_window_days, test_window_days=test_window_days,
        entry_threshold=entry_threshold, exit_threshold=exit_threshold,
        rank_metric=rank_metric,
    )
    report_md = render_sweep_markdown(strategy, candidates, rank_metric)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"sweep-{strategy}-{start_date}-{end_date}.md"
    report_path.write_text(report_md)
    typer.echo(report_md)
    typer.echo(f"Report written to {report_path}")


@app.command("run-daily")
def run_daily(
    as_of: str = typer.Option(None, "--as-of", help="YYYY-MM-DD, defaults to today"),
    lookback_days: int = 250,
    output_dir: Path = typer.Option(REPO_ROOT / "reports", "--output-dir"),
) -> None:
    """Fetches a fresh trailing window directly from Alpaca/EDGAR -- no
    persisted DB dependency, by design (CLAUDE.md invariant #3) -- and
    writes today's ranked signal report."""
    settings = get_settings()
    watchlist = get_watchlist()
    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    window_start, window_end = trailing_window(as_of_date, lookback_days)

    bar_client = AlpacaBarClient(settings)
    bars = bar_client.fetch_daily_bars(watchlist.tickers, window_start, window_end)
    if bars.empty:
        typer.echo("No bars returned from Alpaca -- aborting.", err=True)
        raise typer.Exit(1)

    edgar_client = EdgarClient(settings)
    cusip_to_ticker = _load_cusip_to_ticker()

    transactions = []
    for ticker in watchlist.tickers:
        transactions.extend(fetch_insider_transactions(edgar_client, ticker))
    holdings = fetch_institutional_holdings(edgar_client, cusip_to_ticker)

    holdings_df = pd.DataFrame([h.model_dump(mode="json") for h in holdings], columns=_HOLDING_COLUMNS)
    transactions_df = pd.DataFrame(
        [t.model_dump(mode="json") for t in transactions], columns=_TRANSACTION_COLUMNS
    )
    # Defends the no-lookahead contract even if --as-of backdates this run;
    # a live EDGAR fetch can otherwise return filings filed after as_of_date.
    if not holdings_df.empty:
        holdings_df = holdings_df[pd.to_datetime(holdings_df["filed_date"]).dt.date <= as_of_date]
    if not transactions_df.empty:
        transactions_df = transactions_df[pd.to_datetime(transactions_df["filed_date"]).dt.date <= as_of_date]

    fundamental_data = FundamentalData(institutional_holdings=holdings_df, insider_transactions=transactions_df)
    strategies = [build_strategy(name) for name in ("momentum", "ma_crossover", "volume_breakout")]
    signals = generate_composite_signals(as_of_date, bars, fundamental_data, strategies)

    md_path, json_path = write_report(as_of_date, signals, output_dir)
    typer.echo(f"Wrote {md_path} and {json_path}")


if __name__ == "__main__":
    app()
