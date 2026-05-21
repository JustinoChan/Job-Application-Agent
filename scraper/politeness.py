"""Polite HTTP layer for source adapters.

Centralizes three habits that keep us from looking abusive to public job
boards and the HN Algolia API:

1. **Inter-request delay** — sleep a configurable interval between
   *every* outbound HTTP call (across all source adapters, not just
   within one), so a 45-entry watchlist takes ~45s of pacing rather
   than hammering 45 hosts back-to-back.
2. **Retry with exponential backoff** — transient 429 / 5xx responses
   get retried with growing waits, plus respect for `Retry-After` headers
   when present.
3. **Hard cap on retries** — fail fast if a host is unhealthy rather
   than looping forever.

Source adapters should call `politeness.get(client, url)` instead of
`client.get(url)` directly.
"""
from __future__ import annotations

import logging
import random
import time

import httpx

log = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class Politeness:
    """Tracks last-request time to enforce inter-request delay globally."""

    def __init__(
        self,
        *,
        inter_request_delay_seconds: float,
        max_retries: int,
        backoff_base_seconds: float = 1.0,
        backoff_cap_seconds: float = 30.0,
    ) -> None:
        self.delay = max(0.0, inter_request_delay_seconds)
        self.max_retries = max(0, max_retries)
        self.backoff_base = backoff_base_seconds
        self.backoff_cap = backoff_cap_seconds
        self._last_request_at: float = 0.0

    def _wait_before_next(self) -> None:
        if self.delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _stamp(self) -> None:
        self._last_request_at = time.monotonic()

    def _retry_after_seconds(self, resp: httpx.Response, attempt: int) -> float:
        """Honor `Retry-After` header if present, else exponential backoff."""
        ra = resp.headers.get("Retry-After")
        if ra:
            try:
                return max(0.0, float(ra))
            except ValueError:
                pass  # date-form Retry-After is rare; fall through to backoff
        # exponential backoff with full jitter
        cap = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        return random.uniform(0, cap)

    def _request(self, client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
        """HTTP request with inter-request delay, retries on transient failures."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._wait_before_next()
            try:
                resp = client.request(method, url, **kwargs)
                self._stamp()
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                self._stamp()
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                wait = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
                wait = random.uniform(0, wait)
                log.warning("transport error on %s (attempt %d/%d): %s; sleeping %.1fs",
                            url, attempt + 1, self.max_retries + 1, exc, wait)
                time.sleep(wait)
                continue

            if resp.status_code in _RETRYABLE_STATUSES and attempt < self.max_retries:
                wait = self._retry_after_seconds(resp, attempt)
                log.warning("retryable status %d on %s (attempt %d/%d); sleeping %.1fs",
                            resp.status_code, url, attempt + 1, self.max_retries + 1, wait)
                time.sleep(wait)
                continue

            return resp

        # Should be unreachable: loop either returns or raises.
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"polite request exhausted retries with no response: {url}")

    def get(self, client: httpx.Client, url: str, **kwargs) -> httpx.Response:
        return self._request(client, "GET", url, **kwargs)

    def post(self, client: httpx.Client, url: str, **kwargs) -> httpx.Response:
        return self._request(client, "POST", url, **kwargs)
