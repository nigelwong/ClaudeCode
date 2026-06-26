from datetime import date

import pandas as pd

from tradesignals.signals.base import FundamentalData, Strategy
from tradesignals.signals.smart_money_overlay import compute_overlay_for_tickers

OVERLAY_WEIGHT = 0.3  # smart-money is a tilt on top of technicals, not an equal vote


def generate_composite_signals(
    as_of_date: date,
    market_data: pd.DataFrame,
    fundamental_data: FundamentalData,
    strategies: list[Strategy],
    overlay_weight: float = OVERLAY_WEIGHT,
) -> pd.DataFrame:
    """Combines technical strategy scores with the smart-money overlay into
    one ranked long/short candidate list. Returns columns: ticker,
    direction, score, rank, components (dict, for explainability)."""
    tickers = sorted(market_data["ticker"].unique())
    overlay_scores = compute_overlay_for_tickers(tickers, fundamental_data)

    components_by_ticker: dict[str, dict] = {t: {} for t in tickers}
    technical_scores: dict[str, list[float]] = {t: [] for t in tickers}

    for strategy in strategies:
        for ticker, components in strategy.score(as_of_date, market_data, fundamental_data).items():
            technical_scores[ticker].append(components.score)
            components_by_ticker[ticker][strategy.name] = {"score": components.score, **components.details}

    rows = []
    for ticker in tickers:
        scores = technical_scores[ticker]
        if not scores:
            continue
        technical_avg = sum(scores) / len(scores)
        overlay = overlay_scores[ticker]
        combined = (1 - overlay_weight) * technical_avg + overlay_weight * overlay.score
        components_by_ticker[ticker]["smart_money_overlay"] = {"score": overlay.score, **overlay.details}
        rows.append(
            {
                "ticker": ticker,
                "direction": "long" if combined >= 0 else "short",
                "score": combined,
                "components": components_by_ticker[ticker],
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("score", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df
