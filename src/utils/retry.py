import asyncio
import logging
import random
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)

async def async_retry(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args,
    **kwargs,
) -> Any:
    """
    Executes an async callable with exponential backoff and jitter.
    """
    delay = initial_delay
    last_err: Exception = None

    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as err:
            last_err = err
            if attempt == max_retries:
                logger.warning(f"Function {getattr(func, '__name__', str(func))} failed after {max_retries} attempts: {err}")
                raise

            # Add jitter (10-30%)
            jitter = delay * random.uniform(0.1, 0.3)
            sleep_time = delay + jitter
            logger.debug(f"Attempt {attempt}/{max_retries} failed ({err}). Retrying in {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)
            delay *= backoff_factor

    if last_err:
        raise last_err
