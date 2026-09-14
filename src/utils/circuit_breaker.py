import asyncio
import logging
import time
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    """Raised when a call is attempted on an open circuit breaker."""
    pass

class CircuitBreaker:
    """
    Circuit breaker to isolate scraper and external service failures.
    
    States:
    - CLOSED: Normal operation. Successes reset failure count.
    - OPEN: Calls immediately fail/return fallback without invoking target.
    - HALF_OPEN: Test execution allowed to probe service recovery.
    """
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        recovery_timeout: float = 300.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"
        self._lock = asyncio.Lock()

    @property
    def is_open(self) -> bool:
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN (probing recovery).")
                return False
            return True
        return False

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function guarded by the circuit breaker."""
        async with self._lock:
            if self.is_open:
                logger.warning(f"Circuit breaker '{self.name}' is OPEN. Skipping call.")
                raise CircuitBreakerOpenException(f"Circuit breaker '{self.name}' is OPEN.")

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                self._on_success()
            return result
        except Exception as err:
            async with self._lock:
                self._on_failure(err)
            raise

    def _on_success(self):
        if self.state != "CLOSED":
            logger.info(f"Circuit breaker '{self.name}' recovered: transitioned to CLOSED.")
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self, err: Exception):
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.error(f"Circuit breaker '{self.name}' recorded failure ({self.failure_count}/{self.failure_threshold}): {err}")
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker '{self.name}' tripped: transitioned to OPEN (backoff {self.recovery_timeout}s).")
