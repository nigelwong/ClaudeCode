import time
from datetime import date

import pandas as pd
import requests

from tradesignals.config import Settings

_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
_MIN_INTERVAL_SECONDS = 60.0 / 120  # FRED's documented ceiling is ~120 req/min

# Series tracked by the market-outlook layer's volatility/macro-stress signal.
MACRO_SERIES = {
    "vix": "VIXCLS",  # CBOE Volatility Index
    "yield_curve": "T10Y2Y",  # 10Y-2Y Treasury spread; <= 0 is an inversion
    "credit_spread": "BAMLH0A0HYM2",  # ICE BofA high-yield OAS
}


def parse_observations(series_id: str, payload: dict) -> pd.DataFrame:
    """Returns columns: series_id, date, value. Rows whose value is FRED's
    literal missing-value marker "." are dropped rather than coerced."""
    rows = [
        {"series_id": series_id, "date": obs["date"], "value": float(obs["value"])}
        for obs in payload.get("observations", [])
        if obs["value"] != "."
    ]
    return pd.DataFrame(rows, columns=["series_id", "date", "value"])


class FredClient:
    """Thin wrapper around the free FRED (St. Louis Fed) observations API,
    self-throttled the same way edgar_client.py is throttled for EDGAR."""

    def __init__(self, settings: Settings):
        if not settings.fred_api_key:
            raise ValueError(
                "FRED_API_KEY must be set -- sign up for a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self._api_key = settings.fred_api_key
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)

    def fetch_series(self, series_id: str, start: date, end: date) -> pd.DataFrame:
        self._throttle()
        response = requests.get(
            _BASE_URL,
            params={
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
            },
            timeout=30,
        )
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return parse_observations(series_id, response.json())
