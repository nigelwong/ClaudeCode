import time

import requests

from tradesignals.config import Settings

_MIN_INTERVAL_SECONDS = 1.0 / 10  # SEC's documented ceiling is ~10 req/s


class EdgarClient:
    """HTTP wrapper enforcing SEC EDGAR's access rules: a real identifying
    User-Agent on every request (or you get blocked), and self-throttling
    well under the rate limit (or you risk a temporary IP ban)."""

    def __init__(self, settings: Settings):
        if not settings.sec_edgar_user_agent:
            raise ValueError(
                "SEC_EDGAR_USER_AGENT must be set to a real name+email, e.g. "
                "'Your Name your.email@example.com' -- SEC EDGAR blocks requests without one."
            )
        self._headers = {"User-Agent": settings.sec_edgar_user_agent}
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)

    def get(self, url: str, max_retries: int = 5) -> requests.Response:
        backoff = 1.0
        response: requests.Response | None = None
        for _ in range(max_retries):
            self._throttle()
            response = requests.get(url, headers=self._headers, timeout=30)
            self._last_request_at = time.monotonic()
            if response.status_code == 429:
                time.sleep(backoff)
                backoff *= 2
                continue
            response.raise_for_status()
            return response
        assert response is not None
        response.raise_for_status()
        return response
