from datetime import date, timedelta

import pandas as pd
import pytest

from tradesignals.backtest import sweep as sweep_module
from tradesignals.backtest.sweep import sweep
from tradesignals.backtest.validation import train_test_split, walk_forward_splits

_EMPTY = pd.DataFrame(columns=["ticker", "filed_date"])


def test_train_test_split_no_overlap():
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    split = train_test_split(start, end)

    assert split.train_start == start
    assert split.test_end == end
    assert split.train_end < split.test_start
    assert split.test_start == split.train_end + timedelta(days=1)


def test_walk_forward_splits_tile_without_overlap():
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    splits = walk_forward_splits(start, end, train_window_days=90, test_window_days=30)

    assert len(splits) > 1
    for fold in splits:
        assert fold.train_end < fold.test_start
        assert fold.test_end <= end

    for current, nxt in zip(splits, splits[1:]):
        assert nxt.test_start == current.test_end + timedelta(days=1)


def test_walk_forward_splits_train_windows_may_overlap_across_folds():
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    splits = walk_forward_splits(start, end, train_window_days=200, test_window_days=30)

    assert len(splits) > 1
    # A large train window relative to the test window deliberately
    # produces overlapping train windows across folds -- allowed by design.
    assert splits[1].train_start < splits[0].train_end


def test_sweep_grid_mode_covers_full_cartesian_product(monkeypatch):
    seen_params = []

    def fake_evaluate_split(strategy_name, params, bars, holdings, transactions, fold, entry_threshold, exit_threshold, costs):
        seen_params.append(dict(params))
        return {"sharpe": 0.0}, {"sharpe": 0.0}

    monkeypatch.setattr(sweep_module, "_evaluate_split", fake_evaluate_split)

    param_grid = {"short_window": [5, 10], "long_window": [20, 30]}
    sweep("ma_crossover", param_grid, _EMPTY, _EMPTY, _EMPTY, date(2024, 1, 1), date(2024, 12, 31), mode="grid")

    expected_combos = {
        (5, 20), (5, 30), (10, 20), (10, 30),
    }
    actual_combos = {(p["short_window"], p["long_window"]) for p in seen_params}
    assert actual_combos == expected_combos


def test_sweep_random_mode_samples_subset_deterministically(monkeypatch):
    def fake_evaluate_split(strategy_name, params, bars, holdings, transactions, fold, entry_threshold, exit_threshold, costs):
        return {"sharpe": 0.0}, {"sharpe": 0.0}

    monkeypatch.setattr(sweep_module, "_evaluate_split", fake_evaluate_split)

    param_grid = {"short_window": [5, 10, 15, 20, 25], "long_window": [30, 40, 50]}

    candidates_a = sweep(
        "ma_crossover", param_grid, _EMPTY, _EMPTY, _EMPTY, date(2024, 1, 1), date(2024, 12, 31),
        mode="random", n_samples=4, seed=7,
    )
    candidates_b = sweep(
        "ma_crossover", param_grid, _EMPTY, _EMPTY, _EMPTY, date(2024, 1, 1), date(2024, 12, 31),
        mode="random", n_samples=4, seed=7,
    )

    assert len(candidates_a) == 4
    combos_a = {(c.params["short_window"], c.params["long_window"]) for c in candidates_a}
    combos_b = {(c.params["short_window"], c.params["long_window"]) for c in candidates_b}
    assert combos_a == combos_b


def test_sweep_ranks_by_out_of_sample_metric_only(monkeypatch):
    # Test sharpe deliberately disagrees with train sharpe so a ranking
    # bug that sorted on train metrics instead would be caught.
    test_sharpe_by_window = {5: 0.2, 10: 0.9, 15: 0.1}
    train_sharpe_by_window = {5: 0.9, 10: 0.1, 15: 0.5}

    def fake_evaluate_split(strategy_name, params, bars, holdings, transactions, fold, entry_threshold, exit_threshold, costs):
        window = params["short_window"]
        return {"sharpe": train_sharpe_by_window[window]}, {"sharpe": test_sharpe_by_window[window]}

    monkeypatch.setattr(sweep_module, "_evaluate_split", fake_evaluate_split)

    param_grid = {"short_window": [5, 10, 15]}
    candidates = sweep(
        "ma_crossover", param_grid, _EMPTY, _EMPTY, _EMPTY, date(2024, 1, 1), date(2024, 12, 31), mode="grid",
    )

    ranked_windows = [c.params["short_window"] for c in candidates]
    assert ranked_windows == [10, 5, 15]  # descending by test sharpe: 0.9, 0.2, 0.1
