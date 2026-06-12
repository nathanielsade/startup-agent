import time
from collections.abc import Callable

import httpx

JsonFetcher = Callable[[str], dict]


class HttpJsonFetcher:
    """Callable that GETs a URL and returns parsed JSON, with retry/backoff."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        retries: int = 3,
        backoff: float = 0.5,
        delay: float = 0.0,
        timeout: float = 15.0,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": "startup-agent/0.1"}
        )
        self._retries = retries
        self._backoff = backoff
        self._delay = delay

    def __call__(self, url: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._retries):
            try:
                response = self._client.get(url)
                response.raise_for_status()
                if self._delay:
                    time.sleep(self._delay)
                return response.json()
            except httpx.HTTPError as error:
                last_error = error
                if self._backoff:
                    time.sleep(self._backoff * (attempt + 1))
        assert last_error is not None
        raise last_error
