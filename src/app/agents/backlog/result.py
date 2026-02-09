"""
Node Result Type
=================
Consistent result/error types for all agent nodes.

This module provides a unified way for nodes to report success or failure,
making error handling explicit and consistent across the entire agent.

Example Usage:
    # In a node
    async def __call__(self, state: BacklogAgentState) -> NodeResult[DecompositionResult]:
        try:
            result = await self._decompose(state)
            return NodeResult.ok(result, state_updates={"stories": result.stories})
        except ValidationError as e:
            return NodeResult.err(NodeError.validation(str(e)))

    # Consuming the result
    result = await node(state)
    if result.is_ok:
        new_state = {**state, **result.state_updates}
    else:
        logger.error(f"Node failed: {result.error}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class NodeErrorCode(str, Enum):
    """Categorized error codes for node operations."""

    # Input errors
    VALIDATION_ERROR = "validation_error"
    MISSING_INPUT = "missing_input"
    INVALID_STATE = "invalid_state"

    # Processing errors
    LLM_ERROR = "llm_error"
    PARSING_ERROR = "parsing_error"
    TIMEOUT = "timeout"

    # External service errors
    JIRA_ERROR = "jira_error"
    API_ERROR = "api_error"

    # Business logic errors
    DUPLICATE_DETECTED = "duplicate_detected"
    LOCKED_THREAD = "locked_thread"
    NO_STORIES = "no_stories"

    # System errors
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN = "unknown"


@dataclass
class NodeError:
    """
    Structured error from a node operation.

    Provides a consistent error format across all nodes for logging,
    user feedback, and error recovery.
    """

    code: NodeErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    original_exception: Exception | None = None

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
        }

    # =========================================================================
    # Factory Methods for Common Errors
    # =========================================================================

    @classmethod
    def validation(cls, message: str, **details) -> NodeError:
        """Create a validation error."""
        return cls(
            code=NodeErrorCode.VALIDATION_ERROR,
            message=message,
            details=details,
            recoverable=True,
        )

    @classmethod
    def missing_input(cls, field_name: str) -> NodeError:
        """Create a missing input error."""
        return cls(
            code=NodeErrorCode.MISSING_INPUT,
            message=f"Required input missing: {field_name}",
            details={"field": field_name},
            recoverable=True,
        )

    @classmethod
    def invalid_state(cls, message: str) -> NodeError:
        """Create an invalid state error."""
        return cls(
            code=NodeErrorCode.INVALID_STATE,
            message=message,
            recoverable=False,
        )

    @classmethod
    def llm_error(cls, message: str, exception: Exception | None = None) -> NodeError:
        """Create an LLM error."""
        return cls(
            code=NodeErrorCode.LLM_ERROR,
            message=message,
            recoverable=True,
            original_exception=exception,
        )

    @classmethod
    def parsing_error(cls, message: str, raw_output: str | None = None) -> NodeError:
        """Create a parsing error."""
        return cls(
            code=NodeErrorCode.PARSING_ERROR,
            message=message,
            details={"raw_output": raw_output[:500] if raw_output else None},
            recoverable=True,
        )

    @classmethod
    def jira_error(cls, message: str, status_code: int | None = None) -> NodeError:
        """Create a Jira error."""
        return cls(
            code=NodeErrorCode.JIRA_ERROR,
            message=message,
            details={"status_code": status_code} if status_code else {},
            recoverable=True,
        )

    @classmethod
    def timeout(cls, operation: str, timeout_seconds: float) -> NodeError:
        """Create a timeout error."""
        return cls(
            code=NodeErrorCode.TIMEOUT,
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            recoverable=True,
        )

    @classmethod
    def locked_thread(cls, thread_id: str) -> NodeError:
        """Create a locked thread error."""
        return cls(
            code=NodeErrorCode.LOCKED_THREAD,
            message=f"Thread {thread_id} is locked. Please create a new conversation to make changes.",
            details={"thread_id": thread_id},
            recoverable=False,
        )

    @classmethod
    def no_stories(cls, message: str = "No stories available for this operation") -> NodeError:
        """Create a no stories error."""
        return cls(
            code=NodeErrorCode.NO_STORIES,
            message=message,
            recoverable=True,
        )

    @classmethod
    def internal(cls, message: str, exception: Exception | None = None) -> NodeError:
        """Create an internal error."""
        return cls(
            code=NodeErrorCode.INTERNAL_ERROR,
            message=message,
            recoverable=False,
            original_exception=exception,
        )


@dataclass
class NodeResult(Generic[T]):
    """
    A Result type for node operations.

    Wraps either a successful value with optional state updates,
    or an error with detailed information.

    Usage:
        # Success with state updates
        return NodeResult.ok(
            result,
            state_updates={"stories": result.stories, "current_result": result}
        )

        # Error
        return NodeResult.err(NodeError.validation("Invalid input"))

        # Checking result
        if result.is_ok:
            new_state = {**state, **result.state_updates}
        else:
            logger.error(result.error)
    """

    _value: T | None = None
    _error: NodeError | None = None
    state_updates: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        """Check if the result is successful."""
        return self._error is None

    @property
    def is_error(self) -> bool:
        """Check if the result is an error."""
        return self._error is not None

    @property
    def value(self) -> T:
        """
        Get the success value.

        Raises ValueError if the result is an error.
        """
        if self._error is not None:
            raise ValueError(f"Cannot get value from error result: {self._error}")
        return self._value  # type: ignore

    @property
    def error(self) -> NodeError:
        """
        Get the error.

        Raises ValueError if the result is successful.
        """
        if self._error is None:
            raise ValueError("Cannot get error from successful result")
        return self._error

    def unwrap_or(self, default: T) -> T:
        """Get the value or return a default if error."""
        return self._value if self.is_ok else default

    def map(self, fn) -> NodeResult:
        """Transform the value if successful, pass through error otherwise."""
        if self.is_ok:
            return NodeResult.ok(fn(self._value), state_updates=self.state_updates)
        return self

    def to_state_update(self) -> dict[str, Any]:
        """
        Convert result to state update dict.

        For successful results, returns state_updates.
        For errors, returns an error state update.
        """
        if self.is_ok:
            return self.state_updates
        return {"error": self._error.message}

    @classmethod
    def ok(cls, value: T, state_updates: dict[str, Any] | None = None) -> NodeResult[T]:
        """Create a successful result with optional state updates."""
        return cls(_value=value, state_updates=state_updates or {})

    @classmethod
    def err(cls, error: NodeError) -> NodeResult[T]:
        """Create an error result."""
        return cls(_error=error)

    @classmethod
    def from_exception(cls, exception: Exception, recoverable: bool = True) -> NodeResult[T]:
        """Create an error result from an exception."""
        return cls(
            _error=NodeError(
                code=NodeErrorCode.INTERNAL_ERROR,
                message=str(exception),
                recoverable=recoverable,
                original_exception=exception,
            )
        )


# =============================================================================
# Utility Functions and Decorators
# =============================================================================


import functools
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[dict]])


def with_node_result(node_name: str):
    """
    Decorator to wrap a node's __call__ method with NodeResult handling.

    This decorator allows gradual adoption of NodeResult by wrapping
    existing nodes that return dicts. It catches exceptions and
    converts them to NodeResult.err() automatically.

    Example:
        class DecomposeNode:
            @with_node_result("decompose")
            async def __call__(self, state: BacklogAgentState) -> dict:
                # Existing dict return still works
                return {"stories": [...], "current_result": result}

    The decorator:
    - Logs entry/exit with timing
    - Catches exceptions and returns NodeResult.err()
    - Converts dict returns to NodeResult.ok() with state_updates
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import time

            logger.info(f"Node {node_name}: Starting execution")
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)

                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"Node {node_name}: Completed in {duration_ms:.2f}ms")

                # If already a NodeResult, return as-is
                if isinstance(result, NodeResult):
                    return result

                # Convert dict to NodeResult.ok() with state_updates
                if isinstance(result, dict):
                    return NodeResult.ok(result, state_updates=result)

                return NodeResult.ok(result)

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"Node {node_name}: Failed after {duration_ms:.2f}ms - {e}")
                return NodeResult.from_exception(e)

        return wrapper  # type: ignore

    return decorator


def ensure_state_has_stories(state: dict, node_name: str) -> NodeResult[None] | None:
    """
    Pre-check helper for nodes that require stories in state.

    Returns NodeResult.err() if stories are missing, None otherwise.

    Example:
        error = ensure_state_has_stories(state, "refine")
        if error:
            return error.to_state_update()
    """
    if not state.get("stories"):
        return NodeResult.err(
            NodeError.no_stories(f"{node_name} requires existing stories. Please decompose an epic first.")
        )
    return None


def ensure_state_has_input(state: dict, field: str, node_name: str) -> NodeResult[None] | None:
    """
    Pre-check helper for nodes that require specific input fields.

    Returns NodeResult.err() if field is missing, None otherwise.
    """
    if not state.get(field):
        return NodeResult.err(NodeError.missing_input(field))
    return None
