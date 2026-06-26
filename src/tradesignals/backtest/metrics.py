import numpy as np
import pandas as pd


def total_return(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    return float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)


def annualized_return(equity_curve: pd.Series, trading_days_per_year: int = 252) -> float:
    if len(equity_curve) < 2:
        return 0.0
    growth = equity_curve.iloc[-1] / equity_curve.iloc[0]
    n_days = len(equity_curve) - 1
    if n_days <= 0 or growth <= 0:
        return 0.0
    return float(growth ** (trading_days_per_year / n_days) - 1)


def win_rate(trade_pnls: list[float]) -> float:
    if not trade_pnls:
        return 0.0
    return sum(1 for pnl in trade_pnls if pnl > 0) / len(trade_pnls)


def sharpe_ratio(daily_returns: pd.Series, trading_days_per_year: int = 252, risk_free_rate: float = 0.0) -> float:
    if len(daily_returns) < 2:
        return 0.0
    excess = daily_returns - risk_free_rate / trading_days_per_year
    std = excess.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(trading_days_per_year))


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    return float(drawdown.min())


def compute_metrics(equity_curve: pd.Series, trade_pnls: list[float]) -> dict[str, float]:
    daily_returns = equity_curve.pct_change().dropna()
    return {
        "total_return": total_return(equity_curve),
        "annualized_return": annualized_return(equity_curve),
        "win_rate": win_rate(trade_pnls),
        "sharpe": sharpe_ratio(daily_returns),
        "max_drawdown": max_drawdown(equity_curve),
    }
