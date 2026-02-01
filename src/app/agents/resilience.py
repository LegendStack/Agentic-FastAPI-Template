"""
Resilience Patterns.
====================
Retry, circuit breaker, and timeout patterns for reliable LLM calls.

These patterns ensure stability when calling external APIs that may
be temporarily unavailable or rate-limited.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """States for circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: float = 60.0  # Time before trying half-open


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by failing fast when a service is unhealthy.

    Usage:
        breaker = CircuitBreaker()

        async with breaker:
            result = await call_external_api()
    """

    def __init__(self, config: CircuitBreakerConfig | None = None, name: str = "default"):
        self.config = config or CircuitBreakerConfig()
        self.name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, transitioning from OPEN if timeout elapsed."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.config.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(f"Circuit {self.name} transitioned to HALF_OPEN")
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"Circuit {self.name} CLOSED after recovery")
        elif self.state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} re-OPENED after failure in half-open")
        elif self._failure_count >= self.config.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} OPENED after {self._failure_count} failures")

    async def __aenter__(self):
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit {self.name} is OPEN")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure()
        return False


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


async def retry_with_backoff(func: Callable[..., T], config: RetryConfig | None = None, *args, **kwargs) -> T:
    """
    Execute function with exponential backoff retry.

    Usage:
        result = await retry_with_backoff(call_api, RetryConfig(max_attempts=5))
    """
    config = config or RetryConfig()
    last_exception: Exception = Exception("Retry failed")

    for attempt in range(config.max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e

            if attempt == config.max_attempts - 1:
                break

            # Calculate delay with exponential backoff
            delay = min(config.initial_delay * (config.exponential_base**attempt), config.max_delay)

            # Add jitter if enabled
            if config.jitter:
                import random

                delay = delay * (0.5 + random.random())

            logger.warning(f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. Retrying in {delay:.2f}s")
            await asyncio.sleep(delay)

    raise last_exception


def with_retry(config: RetryConfig | None = None):
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @with_retry(RetryConfig(max_attempts=3))
        async def call_api():
            ...
    """
    config = config or RetryConfig()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(func, config, *args, **kwargs)

        return wrapper

    return decorator


def with_circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator for protecting async functions with circuit breaker.

    Usage:
        breaker = CircuitBreaker(name="openai")

        @with_circuit_breaker(breaker)
        async def call_openai():
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with breaker:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


class ResilientClient:
    """
    High-level client wrapper with retry and circuit breaker.

    Usage:
        client = ResilientClient(
            retry_config=RetryConfig(max_attempts=3),
            circuit_config=CircuitBreakerConfig(failure_threshold=5)
        )

        result = await client.execute(call_api, arg1, arg2)
    """

    def __init__(
        self,
        retry_config: RetryConfig | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        name: str = "default",
    ):
        self.retry_config = retry_config or RetryConfig()
        self.breaker = CircuitBreaker(circuit_config, name)

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with retry and circuit breaker protection."""
        async with self.breaker:
            return await retry_with_backoff(func, self.retry_config, *args, **kwargs)

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.breaker.state

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.breaker._state = CircuitState.CLOSED
        self.breaker._failure_count = 0
        self.breaker._success_count = 0
