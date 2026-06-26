import json
from pathlib import Path

import pytest

from tradesignals.data.fred_client import parse_observations

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "fred"


def test_parse_observations_drops_missing_value_marker():
    payload = json.loads((_FIXTURES_DIR / "sample_vix_observations.json").read_text())

    df = parse_observations("VIXCLS", payload)

    # Two of the six fixture rows use FRED's literal "." missing-value
    # marker and must be dropped, not coerced to 0.0 or NaN.
    assert len(df) == 4
    assert set(df["date"]) == {"2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08"}
    assert (df["series_id"] == "VIXCLS").all()
    assert df.loc[df["date"] == "2024-01-03", "value"].iloc[0] == pytest.approx(14.05)


def test_parse_observations_empty_payload_returns_empty_frame():
    df = parse_observations("VIXCLS", {"observations": []})

    assert df.empty
    assert list(df.columns) == ["series_id", "date", "value"]
