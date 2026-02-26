"""Per-domain rate limiter to avoid overloading target sites."""

from __future__ import annotations

import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Async rate limiter that enforces a minimum delay between requests
    to the same domain. Thread-safe for use within a single asyncio loop.
    """

    def __init__(self, domain: str, delay: float = 1.5):
        self.domain = domain
        self.delay = delay
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait until enough time has passed since the last request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.delay:
                wait_time = self.delay - elapsed
                logger.debug("Rate limiting %s: waiting %.1fs", self.domain, wait_time)
                await asyncio.sleep(wait_time)
            self._last_request = time.monotonic()
