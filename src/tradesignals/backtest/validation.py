from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Split:
    train_start: date
    train_end: date
    test_start: date
    test_end: date


def train_test_split(start: date, end: date, train_fraction: float = 0.7) -> Split:
    """A single chronological in-sample/out-of-sample split -- train_end is
    always strictly before test_start, so a fold can never leak future
    data into parameter selection."""
    total_days = (end - start).days
    train_end = start + timedelta(days=int(total_days * train_fraction))
    test_start = train_end + timedelta(days=1)
    return Split(train_start=start, train_end=train_end, test_start=test_start, test_end=end)


def walk_forward_splits(start: date, end: date, train_window_days: int, test_window_days: int) -> list[Split]:
    """Rolling walk-forward folds: each fold's test window is the period
    immediately after its train window, and folds tile forward by
    test_window_days so test periods are contiguous and non-overlapping.
    Train windows may legitimately overlap across folds (that's how
    rolling walk-forward works) -- what must never happen, and is checked
    in tests, is overlap between a single fold's own train and test dates.
    """
    splits = []
    train_start = start
    while True:
        train_end = train_start + timedelta(days=train_window_days)
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test_window_days - 1)
        if test_end > end:
            break
        splits.append(Split(train_start, train_end, test_start, test_end))
        train_start = train_start + timedelta(days=test_window_days)
    return splits
