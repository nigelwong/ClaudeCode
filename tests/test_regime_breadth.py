import pandas as pd

from tradesignals.regime.breadth import compute_breadth


def _bars_for(ticker: str, closes: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"ticker": ticker, "date": dates, "close": closes})


def test_no_ticker_has_enough_history_returns_neutral_default():
    bars = _bars_for("A", [100.0] * 10)
    assert compute_breadth(bars, ["A"]) == 0.5


def test_mixed_participation_excludes_tickers_without_enough_history():
    above_a = _bars_for("A", [100.0 + i for i in range(60)])  # rising -> above 50dma
    below_b = _bars_for("B", [200.0 - i for i in range(60)])  # falling -> below 50dma
    above_c = _bars_for("C", [50.0 + i * 2 for i in range(60)])  # rising -> above 50dma
    insufficient_d = _bars_for("D", [100.0] * 10)  # excluded: < 50 rows

    bars = pd.concat([above_a, below_b, above_c, insufficient_d], ignore_index=True)
    breadth = compute_breadth(bars, ["A", "B", "C", "D"])
    assert breadth == 2 / 3


def test_all_above_is_one():
    above_a = _bars_for("A", [100.0 + i for i in range(60)])
    above_b = _bars_for("B", [50.0 + i * 2 for i in range(60)])
    bars = pd.concat([above_a, above_b], ignore_index=True)
    assert compute_breadth(bars, ["A", "B"]) == 1.0
