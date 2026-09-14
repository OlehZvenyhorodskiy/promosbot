import asyncio
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Asynchronous token bucket / interval rate limiter for HTTP scrapers.
    Prevents IP bans and WAF rate-limit triggers by smoothing out requests.
    """

    def __init__(self, requests_per_second: float = 2.0, burst: int = 5):
        self.rate = requests_per_second
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request token is available."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now

                # Add tokens based on elapsed time
                self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate wait time for the next token
                needed = 1.0 - self.tokens
                wait_time = needed / self.rate
                await asyncio.sleep(wait_time)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class PerDomainRateLimiter:
    """
    Manages per-domain rate limiters to avoid overwhelming individual retailer domains.
    """

    def __init__(self, default_rps: float = 2.0):
        self.default_rps = default_rps
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str) -> None:
        async with self._lock:
            if domain not in self._limiters:
                self._limiters[domain] = RateLimiter(requests_per_second=self.default_rps)
            limiter = self._limiters[domain]
        await limiter.acquire()
