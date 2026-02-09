"""
Observability
=============
Structured logging, timing metrics, and context tracking for the Backlog Agent.

This module provides decorators and utilities for comprehensive observability:
- Structured logging with context (thread_id, user_id, intent)
- Timing metrics for node execution
- Request/response logging for external services

Example Usage:
    from .observability import node_execution, AgentContext

    # Use decorator for automatic timing and logging
    @node_execution("decompose")
    async def process(self, state: BacklogAgentState) -> dict:
        ...

    # Use context for structured logging
    with AgentContext(thread_id="abc-123", user_id="user@example.com"):
        logger.info("Processing request")  # Automatically includes context
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Context Variables
# =============================================================================

# Thread-local context for structured logging
_agent_context: ContextVar[AgentContext | None] = ContextVar("agent_context", default=None)


@dataclass
class AgentContext:
    """
    Context for agent execution.

    Holds metadata that should be included in all log messages
    during a request/thread execution.
    """

    thread_id: str | None = None
    user_id: str | None = None
    conversation_id: str | None = None
    intent: str | None = None
    epic_key: str | None = None
    start_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to a dict for logging."""
        return {
            k: v
            for k, v in {
                "thread_id": self.thread_id,
                "user_id": self.user_id,
                "conversation_id": self.conversation_id,
                "intent": self.intent,
                "epic_key": self.epic_key,
            }.items()
            if v is not None
        }

    def __enter__(self) -> AgentContext:
        """Set this context as the current context."""
        self._token = _agent_context.set(self)
        return self

    def __exit__(self, *args) -> None:
        """Restore the previous context."""
        _agent_context.reset(self._token)


def get_current_context() -> AgentContext | None:
    """Get the current agent context, if any."""
    return _agent_context.get()


# =============================================================================
# Metrics Collection
# =============================================================================


@dataclass
class NodeMetrics:
    """Metrics for a single node execution."""

    node_name: str
    duration_ms: float
    success: bool
    error_type: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_name": self.node_name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_type": self.error_type,
            "timestamp": self.timestamp.isoformat(),
        }


class MetricsCollector:
    """
    Collects and aggregates execution metrics.

    Thread-safe collection of node execution metrics.
    Can be used to track performance and identify bottlenecks.
    """

    def __init__(self):
        self._metrics: list[NodeMetrics] = []
        self._start_time: datetime | None = None

    def start_request(self) -> None:
        """Mark the start of a request."""
        self._start_time = datetime.now()
        self._metrics = []

    def record_node(self, metrics: NodeMetrics) -> None:
        """Record metrics for a node execution."""
        self._metrics.append(metrics)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of collected metrics."""
        if not self._metrics:
            return {"nodes": [], "total_duration_ms": 0}

        total_duration = sum(m.duration_ms for m in self._metrics)
        success_rate = sum(1 for m in self._metrics if m.success) / len(self._metrics)

        return {
            "nodes": [m.to_dict() for m in self._metrics],
            "total_duration_ms": total_duration,
            "node_count": len(self._metrics),
            "success_rate": success_rate,
            "slowest_node": max(self._metrics, key=lambda m: m.duration_ms).node_name,
        }


# Global metrics collector (thread-safe via ContextVar would be better in production)
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector


# =============================================================================
# Logging Utilities
# =============================================================================


class StructuredLogger:
    """
    A logger that includes agent context in all messages.

    Wraps the standard logger to automatically include
    thread_id, user_id, and other context fields.
    """

    def __init__(self, base_logger: logging.Logger):
        self._logger = base_logger

    def _add_context(self, msg: str, extra: dict | None = None) -> tuple[str, dict]:
        """Add context to log message."""
        ctx = get_current_context()
        ctx_dict = ctx.to_dict() if ctx else {}

        if extra:
            ctx_dict.update(extra)

        if ctx_dict:
            ctx_str = " ".join(f"{k}={v}" for k, v in ctx_dict.items())
            msg = f"[{ctx_str}] {msg}"

        return msg, ctx_dict

    def info(self, msg: str, **extra) -> None:
        msg, _ = self._add_context(msg, extra)
        self._logger.info(msg)

    def warning(self, msg: str, **extra) -> None:
        msg, _ = self._add_context(msg, extra)
        self._logger.warning(msg)

    def error(self, msg: str, **extra) -> None:
        msg, _ = self._add_context(msg, extra)
        self._logger.error(msg)

    def debug(self, msg: str, **extra) -> None:
        msg, _ = self._add_context(msg, extra)
        self._logger.debug(msg)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger for the given module name."""
    return StructuredLogger(logging.getLogger(name))


# =============================================================================
# Decorators
# =============================================================================


def node_execution(node_name: str):
    """
    Decorator for node __call__ methods.

    Automatically logs entry/exit, timing, and errors.
    Records metrics to the global collector.

    Example:
        class DecomposeNode:
            @node_execution("decompose")
            async def __call__(self, state: BacklogAgentState) -> dict:
                ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            slogger = get_logger(__name__)
            collector = get_metrics_collector()

            slogger.info(f"Node {node_name}: Starting execution")
            start_time = time.perf_counter()
            success = True
            error_type = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                slogger.error(f"Node {node_name}: Failed with {error_type}: {e}")
                raise
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                slogger.info(
                    f"Node {node_name}: Completed in {duration_ms:.2f}ms",
                    duration_ms=duration_ms,
                    success=success,
                )

                metrics = NodeMetrics(
                    node_name=node_name,
                    duration_ms=duration_ms,
                    success=success,
                    error_type=error_type,
                )
                collector.record_node(metrics)

        return wrapper

    return decorator


@contextmanager
def timed_operation(operation_name: str):
    """
    Context manager for timing any operation.

    Example:
        with timed_operation("jira_api_call"):
            response = await client.get(url)
    """
    slogger = get_logger(__name__)
    start = time.perf_counter()

    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        slogger.info(f"{operation_name}: Completed in {duration_ms:.2f}ms")


# =============================================================================
# Request/Response Logging
# =============================================================================


def log_jira_request(
    method: str,
    url: str,
    payload: dict | None = None,
) -> None:
    """Log a Jira API request."""
    slogger = get_logger("jira")
    payload_summary = f" with {len(payload)} fields" if payload else ""
    slogger.info(f"JIRA Request: {method} {url}{payload_summary}")


def log_jira_response(
    method: str,
    url: str,
    status_code: int,
    duration_ms: float,
    success: bool,
) -> None:
    """Log a Jira API response."""
    slogger = get_logger("jira")
    status = "OK" if success else "ERROR"
    slogger.info(f"JIRA Response: {method} {url} -> {status_code} ({status}) in {duration_ms:.2f}ms")
