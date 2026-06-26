import random
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Any

import pandas as pd

from tradesignals.backtest.costs import TransactionCosts
from tradesignals.backtest.engine import run_backtest
from tradesignals.backtest.metrics import compute_metrics
from tradesignals.backtest.validation import Split, train_test_split, walk_forward_splits
from tradesignals.signals.registry import build_strategy


@dataclass
class SweepCandidate:
    params: dict[str, Any]
    train_metrics: dict[str, float]
    test_metrics: dict[str, float]


def _param_combinations(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    names = list(param_grid.keys())
    return [dict(zip(names, values)) for values in product(*param_grid.values())]


def _average_metrics(metric_dicts: list[dict[str, float]]) -> dict[str, float]:
    keys = metric_dicts[0].keys()
    return {key: sum(d[key] for d in metric_dicts) / len(metric_dicts) for key in keys}


def _evaluate_split(
    strategy_name: str,
    params: dict[str, Any],
    bars: pd.DataFrame,
    institutional_holdings: pd.DataFrame,
    insider_transactions: pd.DataFrame,
    split: Split,
    entry_threshold: float,
    exit_threshold: float,
    costs: TransactionCosts,
) -> tuple[dict[str, float], dict[str, float]]:
    strategy = build_strategy(strategy_name, **params)
    train_result = run_backtest(
        strategy, bars, institutional_holdings, insider_transactions,
        start=split.train_start, end=split.train_end,
        entry_threshold=entry_threshold, exit_threshold=exit_threshold, costs=costs,
    )
    test_result = run_backtest(
        strategy, bars, institutional_holdings, insider_transactions,
        start=split.test_start, end=split.test_end,
        entry_threshold=entry_threshold, exit_threshold=exit_threshold, costs=costs,
    )
    train_metrics = compute_metrics(train_result.equity_curve, [t.pnl for t in train_result.trades])
    test_metrics = compute_metrics(test_result.equity_curve, [t.pnl for t in test_result.trades])
    return train_metrics, test_metrics


def sweep(
    strategy_name: str,
    param_grid: dict[str, list[Any]],
    bars: pd.DataFrame,
    institutional_holdings: pd.DataFrame,
    insider_transactions: pd.DataFrame,
    start: date,
    end: date,
    mode: str = "grid",
    n_samples: int = 20,
    seed: int = 42,
    split: str = "train_test",
    train_window_days: int = 365,
    test_window_days: int = 90,
    entry_threshold: float = 0.5,
    exit_threshold: float = 0.0,
    rank_metric: str = "sharpe",
    costs: TransactionCosts | None = None,
) -> list[SweepCandidate]:
    """Every candidate is scored on its own held-out test split(s), and
    ranking always uses the test-set metric -- in-sample performance is
    reported alongside for comparison but never drives selection, since
    that's how a sweep silently turns into curve-fitting."""
    costs = costs or TransactionCosts()

    if split == "train_test":
        splits = [train_test_split(start, end)]
    elif split == "walk_forward":
        splits = walk_forward_splits(start, end, train_window_days, test_window_days)
    else:
        raise ValueError(f"unknown split mode: {split}")
    if not splits:
        raise ValueError("date range too short to produce any train/test split")

    combos = _param_combinations(param_grid)
    if mode == "random":
        rng = random.Random(seed)
        combos = rng.sample(combos, min(n_samples, len(combos)))
    elif mode != "grid":
        raise ValueError(f"unknown sweep mode: {mode}")

    candidates = []
    for params in combos:
        train_runs, test_runs = [], []
        for fold in splits:
            train_metrics, test_metrics = _evaluate_split(
                strategy_name, params, bars, institutional_holdings, insider_transactions, fold,
                entry_threshold, exit_threshold, costs,
            )
            train_runs.append(train_metrics)
            test_runs.append(test_metrics)
        candidates.append(
            SweepCandidate(
                params=params,
                train_metrics=_average_metrics(train_runs),
                test_metrics=_average_metrics(test_runs),
            )
        )

    candidates.sort(key=lambda c: c.test_metrics.get(rank_metric, float("-inf")), reverse=True)
    return candidates
