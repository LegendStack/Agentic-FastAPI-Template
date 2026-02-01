"""
Rate Limiting for Agents.
=========================
Per-tenant token and request rate limiting using Redis or in-memory storage.

Prevents runaway costs from any single tenant while ensuring fair resource allocation.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UsageStats(BaseModel):
    """Current usage statistics for a tenant."""

    tenant_id: str
    tokens_used: int = 0
    requests_made: int = 0
    period_start: datetime
    period_end: datetime
    tokens_limit: int
    requests_limit: int

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.tokens_limit - self.tokens_used)

    @property
    def requests_remaining(self) -> int:
        return max(0, self.requests_limit - self.requests_made)

    @property
    def is_token_limited(self) -> bool:
        return self.tokens_used >= self.tokens_limit

    @property
    def is_request_limited(self) -> bool:
        return self.requests_made >= self.requests_limit


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    tokens_per_minute: int = 100000
    tokens_per_hour: int = 1000000
    tokens_per_day: int = 10000000
    requests_per_minute: int = 100
    requests_per_hour: int = 1000
    requests_per_day: int = 10000

    # Default limits for tenants without custom config
    default_tier: str = "standard"


# Predefined tiers
RATE_LIMIT_TIERS = {
    "free": RateLimitConfig(
        tokens_per_minute=10000,
        tokens_per_hour=50000,
        tokens_per_day=100000,
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=500,
    ),
    "standard": RateLimitConfig(
        tokens_per_minute=100000,
        tokens_per_hour=1000000,
        tokens_per_day=10000000,
        requests_per_minute=100,
        requests_per_hour=1000,
        requests_per_day=10000,
    ),
    "premium": RateLimitConfig(
        tokens_per_minute=500000,
        tokens_per_hour=5000000,
        tokens_per_day=50000000,
        requests_per_minute=500,
        requests_per_hour=5000,
        requests_per_day=50000,
    ),
    "enterprise": RateLimitConfig(
        tokens_per_minute=2000000,
        tokens_per_hour=20000000,
        tokens_per_day=200000000,
        requests_per_minute=2000,
        requests_per_hour=20000,
        requests_per_day=200000,
    ),
}


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class BaseRateLimiter(ABC):
    """Abstract base for rate limiter implementations."""

    @abstractmethod
    async def check_limit(self, tenant_id: str, tokens_requested: int = 1) -> bool:
        """Check if request is within limits. Returns True if allowed."""
        pass

    @abstractmethod
    async def record_usage(self, tenant_id: str, tokens_used: int = 0, requests: int = 1) -> None:
        """Record usage after a request."""
        pass

    @abstractmethod
    async def get_usage(self, tenant_id: str) -> UsageStats:
        """Get current usage stats for a tenant."""
        pass


class InMemoryRateLimiter(BaseRateLimiter):
    """
    In-memory rate limiter using sliding window.

    Good for single-instance deployments. For distributed systems,
    use RedisRateLimiter instead.
    """

    def __init__(self, default_config: RateLimitConfig | None = None):
        self.default_config = default_config or RATE_LIMIT_TIERS["standard"]
        self._tenant_configs: dict[str, RateLimitConfig] = {}
        self._usage: dict[str, dict[str, list]] = {}  # tenant -> window -> [(timestamp, amount)]
        self._lock = asyncio.Lock()

    def set_tenant_tier(self, tenant_id: str, tier: str) -> None:
        """Set rate limit tier for a tenant."""
        if tier in RATE_LIMIT_TIERS:
            self._tenant_configs[tenant_id] = RATE_LIMIT_TIERS[tier]

    def set_tenant_config(self, tenant_id: str, config: RateLimitConfig) -> None:
        """Set custom rate limit config for a tenant."""
        self._tenant_configs[tenant_id] = config

    def _get_config(self, tenant_id: str) -> RateLimitConfig:
        return self._tenant_configs.get(tenant_id, self.default_config)

    def _clean_old_entries(self, entries: list, window_seconds: int) -> list:
        """Remove entries older than the window."""
        cutoff = time.time() - window_seconds
        return [(ts, amt) for ts, amt in entries if ts > cutoff]

    def _sum_window(self, entries: list, window_seconds: int) -> int:
        """Sum usage within a time window."""
        cutoff = time.time() - window_seconds
        return sum(amt for ts, amt in entries if ts > cutoff)

    async def check_limit(self, tenant_id: str, tokens_requested: int = 1) -> bool:
        """Check if request is within all rate limits."""
        async with self._lock:
            config = self._get_config(tenant_id)

            if tenant_id not in self._usage:
                return True

            usage = self._usage[tenant_id]
            token_entries = usage.get("tokens", [])
            request_entries = usage.get("requests", [])

            # Check minute limits
            tokens_minute = self._sum_window(token_entries, 60)
            requests_minute = self._sum_window(request_entries, 60)

            if tokens_minute + tokens_requested > config.tokens_per_minute:
                return False
            if requests_minute + 1 > config.requests_per_minute:
                return False

            # Check hour limits
            tokens_hour = self._sum_window(token_entries, 3600)
            requests_hour = self._sum_window(request_entries, 3600)

            if tokens_hour + tokens_requested > config.tokens_per_hour:
                return False
            if requests_hour + 1 > config.requests_per_hour:
                return False

            return True

    async def record_usage(self, tenant_id: str, tokens_used: int = 0, requests: int = 1) -> None:
        """Record usage."""
        async with self._lock:
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {"tokens": [], "requests": []}

            now = time.time()

            if tokens_used > 0:
                self._usage[tenant_id]["tokens"].append((now, tokens_used))
                # Clean old entries
                self._usage[tenant_id]["tokens"] = self._clean_old_entries(self._usage[tenant_id]["tokens"], 86400)

            if requests > 0:
                self._usage[tenant_id]["requests"].append((now, requests))
                self._usage[tenant_id]["requests"] = self._clean_old_entries(self._usage[tenant_id]["requests"], 86400)

    async def get_usage(self, tenant_id: str) -> UsageStats:
        """Get current usage statistics."""
        config = self._get_config(tenant_id)
        now = datetime.utcnow()

        async with self._lock:
            usage = self._usage.get(tenant_id, {"tokens": [], "requests": []})

            return UsageStats(
                tenant_id=tenant_id,
                tokens_used=self._sum_window(usage.get("tokens", []), 3600),
                requests_made=self._sum_window(usage.get("requests", []), 3600),
                period_start=now - timedelta(hours=1),
                period_end=now,
                tokens_limit=config.tokens_per_hour,
                requests_limit=config.requests_per_hour,
            )


class RedisRateLimiter(BaseRateLimiter):
    """
    Redis-based rate limiter for distributed systems.

    Uses Redis sorted sets for efficient sliding window rate limiting.
    """

    def __init__(self, redis_url: str, default_config: RateLimitConfig | None = None):
        self.redis_url = redis_url
        self.default_config = default_config or RATE_LIMIT_TIERS["standard"]
        self._tenant_configs: dict[str, RateLimitConfig] = {}
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError("redis required. Install with: pip install redis")
        return self._redis

    def set_tenant_tier(self, tenant_id: str, tier: str) -> None:
        if tier in RATE_LIMIT_TIERS:
            self._tenant_configs[tenant_id] = RATE_LIMIT_TIERS[tier]

    def _get_config(self, tenant_id: str) -> RateLimitConfig:
        return self._tenant_configs.get(tenant_id, self.default_config)

    async def check_limit(self, tenant_id: str, tokens_requested: int = 1) -> bool:
        """Check rate limits using Redis."""
        redis = await self._get_redis()
        config = self._get_config(tenant_id)
        now = time.time()

        # Check tokens per minute
        key = f"ratelimit:{tenant_id}:tokens:minute"
        await redis.zremrangebyscore(key, 0, now - 60)
        current = await redis.zcard(key)

        if current + tokens_requested > config.tokens_per_minute:
            return False

        # Check requests per minute
        key = f"ratelimit:{tenant_id}:requests:minute"
        await redis.zremrangebyscore(key, 0, now - 60)
        current = await redis.zcard(key)

        if current + 1 > config.requests_per_minute:
            return False

        return True

    async def record_usage(self, tenant_id: str, tokens_used: int = 0, requests: int = 1) -> None:
        """Record usage in Redis."""
        redis = await self._get_redis()
        now = time.time()

        if tokens_used > 0:
            key = f"ratelimit:{tenant_id}:tokens:minute"
            await redis.zadd(key, {f"{now}:{tokens_used}": now})
            await redis.expire(key, 120)

        if requests > 0:
            key = f"ratelimit:{tenant_id}:requests:minute"
            await redis.zadd(key, {f"{now}": now})
            await redis.expire(key, 120)

    async def get_usage(self, tenant_id: str) -> UsageStats:
        """Get usage from Redis."""
        redis = await self._get_redis()
        config = self._get_config(tenant_id)
        now = datetime.utcnow()

        # Get hourly usage
        tokens_key = f"ratelimit:{tenant_id}:tokens:minute"
        requests_key = f"ratelimit:{tenant_id}:requests:minute"

        tokens_used = await redis.zcard(tokens_key)
        requests_made = await redis.zcard(requests_key)

        return UsageStats(
            tenant_id=tenant_id,
            tokens_used=tokens_used,
            requests_made=requests_made,
            period_start=now - timedelta(minutes=1),
            period_end=now,
            tokens_limit=config.tokens_per_minute,
            requests_limit=config.requests_per_minute,
        )


class TenantRateLimiter:
    """
    High-level rate limiter with pluggable backend.

    Usage:
        limiter = TenantRateLimiter()

        # Check before making request
        if not await limiter.check_limit("tenant-123", tokens=1000):
            raise RateLimitExceeded("Quota exceeded")

        # Record usage after request
        await limiter.record_usage("tenant-123", tokens=1234)
    """

    def __init__(self, backend: BaseRateLimiter | None = None):
        self._backend = backend or InMemoryRateLimiter()

    def set_backend(self, backend: BaseRateLimiter) -> None:
        """Switch rate limiting backend."""
        self._backend = backend

    def set_tenant_tier(self, tenant_id: str, tier: str) -> None:
        """Set rate limit tier for a tenant."""
        if hasattr(self._backend, "set_tenant_tier"):
            self._backend.set_tenant_tier(tenant_id, tier)

    async def check_limit(self, tenant_id: str, tokens_requested: int = 1) -> bool:
        """Check if request is within limits."""
        return await self._backend.check_limit(tenant_id, tokens_requested)

    async def record_usage(self, tenant_id: str, tokens_used: int = 0, requests: int = 1) -> None:
        """Record usage after request completion."""
        await self._backend.record_usage(tenant_id, tokens_used, requests)

    async def get_usage(self, tenant_id: str) -> UsageStats:
        """Get current usage for a tenant."""
        return await self._backend.get_usage(tenant_id)

    async def enforce_limit(self, tenant_id: str, tokens_requested: int = 1) -> None:
        """Check limit and raise if exceeded."""
        if not await self.check_limit(tenant_id, tokens_requested):
            usage = await self.get_usage(tenant_id)
            raise RateLimitExceeded(
                f"Rate limit exceeded for {tenant_id}. "
                f"Tokens: {usage.tokens_used}/{usage.tokens_limit}, "
                f"Requests: {usage.requests_made}/{usage.requests_limit}",
                retry_after=60,
            )


# Global default limiter
rate_limiter = TenantRateLimiter()
