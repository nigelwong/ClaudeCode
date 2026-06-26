import statistics

import math
import pandas as pd
import pytest

from tradesignals.backtest.metrics import (
    annualized_return,
    compute_metrics,
    max_drawdown,
    sharpe_ratio,
    total_return,
    win_rate,
)


def test_total_return_hand_computed():
    equity_curve = pd.Series([100.0, 110.0, 121.0])
    assert total_return(equity_curve) == pytest.approx(0.21)


def test_total_return_too_short_is_zero():
    assert total_return(pd.Series([100.0])) == 0.0


def test_annualized_return_hand_computed_with_clean_exponent():
    # 3 points -> n_days=2; trading_days_per_year=2 makes the exponent 1,
    # collapsing the formula to growth - 1 for a clean expected value.
    equity_curve = pd.Series([100.0, 110.0, 121.0])
    result = annualized_return(equity_curve, trading_days_per_year=2)
    assert result == pytest.approx(0.21)


def test_annualized_return_negative_growth_is_zero():
    equity_curve = pd.Series([100.0, -10.0])
    assert annualized_return(equity_curve) == 0.0


def test_annualized_return_too_short_is_zero():
    assert annualized_return(pd.Series([100.0])) == 0.0


def test_win_rate_hand_computed():
    # 2 of 5 strictly positive (zero PnL does not count as a win)
    assert win_rate([10.0, -5.0, 20.0, -1.0, 0.0]) == pytest.approx(0.4)


def test_win_rate_empty_is_zero():
    assert win_rate([]) == 0.0


def test_sharpe_ratio_matches_independent_computation():
    daily_returns = pd.Series([0.02, 0.04, -0.01, 0.03])
    expected = (
        statistics.mean(daily_returns)
        / statistics.stdev(daily_returns)
        * math.sqrt(252)
    )
    assert sharpe_ratio(daily_returns) == pytest.approx(expected)


def test_sharpe_ratio_too_short_is_zero():
    assert sharpe_ratio(pd.Series([0.01])) == 0.0


def test_sharpe_ratio_zero_std_is_zero():
    assert sharpe_ratio(pd.Series([0.01, 0.01, 0.01])) == 0.0


def test_max_drawdown_hand_computed():
    equity_curve = pd.Series([100.0, 120.0, 90.0, 110.0, 80.0, 130.0])
    assert max_drawdown(equity_curve) == pytest.approx(-1 / 3)


def test_max_drawdown_empty_is_zero():
    assert max_drawdown(pd.Series([], dtype=float)) == 0.0


def test_compute_metrics_matches_individual_functions():
    equity_curve = pd.Series([100.0, 110.0, 121.0, 108.0])
    trade_pnls = [10.0, -5.0]
    daily_returns = equity_curve.pct_change().dropna()

    result = compute_metrics(equity_curve, trade_pnls)

    assert set(result.keys()) == {"total_return", "annualized_return", "win_rate", "sharpe", "max_drawdown"}
    assert result["total_return"] == pytest.approx(total_return(equity_curve))
    assert result["annualized_return"] == pytest.approx(annualized_return(equity_curve))
    assert result["win_rate"] == pytest.approx(win_rate(trade_pnls))
    assert result["sharpe"] == pytest.approx(sharpe_ratio(daily_returns))
    assert result["max_drawdown"] == pytest.approx(max_drawdown(equity_curve))
