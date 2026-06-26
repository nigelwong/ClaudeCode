import json

from tradesignals.data.edgar_client import EdgarClient

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_cache: dict[str, str] | None = None


def _ticker_to_cik_map(client: EdgarClient) -> dict[str, str]:
    global _cache
    if _cache is None:
        response = client.get(_TICKERS_URL)
        payload = json.loads(response.text)
        _cache = {entry["ticker"]: str(entry["cik_str"]).zfill(10) for entry in payload.values()}
    return _cache


def cik_for_ticker(client: EdgarClient, ticker: str) -> str | None:
    return _ticker_to_cik_map(client).get(ticker.upper())
