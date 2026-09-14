import asyncio
import time
import pytest
from src.utils.rate_limiter import RateLimiter, PerDomainRateLimiter
from src.utils.retry import async_retry

@pytest.mark.asyncio
async def test_rate_limiter_acquire():
    # 10 rps with 1 burst
    limiter = RateLimiter(requests_per_second=10.0, burst=1)
    t0 = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    t1 = time.monotonic()
    # Second acquire should take ~0.1s
    assert (t1 - t0) >= 0.08

@pytest.mark.asyncio
async def test_per_domain_rate_limiter():
    manager = PerDomainRateLimiter(default_rps=20.0)
    await manager.acquire("colruyt.be")
    await manager.acquire("delhaize.be")
    assert "colruyt.be" in manager._limiters
    assert "delhaize.be" in manager._limiters

@pytest.mark.asyncio
async def test_async_retry_success():
    attempts = 0
    async def sample():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("temporary error")
        return "success"

    res = await async_retry(sample, max_retries=3, initial_delay=0.01, backoff_factor=1.5)
    assert res == "success"
    assert attempts == 2

@pytest.mark.asyncio
async def test_async_retry_exhausted():
    async def failing():
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError):
        await async_retry(failing, max_retries=2, initial_delay=0.01)
