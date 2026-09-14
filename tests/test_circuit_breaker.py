import pytest
import asyncio
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException

@pytest.mark.asyncio
async def test_circuit_breaker_success():
    cb = CircuitBreaker(name="test_success", failure_threshold=2)
    
    async def sample_task():
        return "success"
    
    result = await cb.call(sample_task)
    assert result == "success"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0

@pytest.mark.asyncio
async def test_circuit_breaker_tripping():
    cb = CircuitBreaker(name="test_trip", failure_threshold=2, recovery_timeout=0.2)
    
    async def failing_task():
        raise RuntimeError("Website down")
    
    # First failure
    with pytest.raises(RuntimeError):
        await cb.call(failing_task)
    assert cb.state == "CLOSED"
    assert cb.failure_count == 1

    # Second failure trips to OPEN
    with pytest.raises(RuntimeError):
        await cb.call(failing_task)
    assert cb.state == "OPEN"

    # Subsequent call immediately raises CircuitBreakerOpenException without invoking target
    with pytest.raises(CircuitBreakerOpenException):
        await cb.call(failing_task)

    # Wait for recovery timeout
    await asyncio.sleep(0.25)
    assert cb.is_open is False
    assert cb.state == "HALF_OPEN"

    # Recovery on success
    async def healthy_task():
        return "recovered"

    result = await cb.call(healthy_task)
    assert result == "recovered"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0
