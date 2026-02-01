"""
Cost tracking for LLM operations.
Stores per-request token usage and estimated costs for billing/analytics.
"""

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa

from ..core.db.database import Base


class LLMCostRecord(Base):
    """Tracks token usage and costs for LLM API calls."""

    __tablename__ = "llm_cost_records"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    # Request identification
    request_id = sa.Column(sa.String(64), index=True, nullable=False)
    thread_id = sa.Column(sa.String(64), index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), index=True)
    tenant_id = sa.Column(sa.String(64), index=True)

    # Model info
    provider = sa.Column(sa.String(32), default="azure_openai")
    model_name = sa.Column(sa.String(64), nullable=False)
    operation = sa.Column(sa.String(32), default="chat")  # chat, embedding, etc.

    # Token usage
    input_tokens = sa.Column(sa.Integer, default=0)
    output_tokens = sa.Column(sa.Integer, default=0)
    total_tokens = sa.Column(sa.Integer, default=0)

    # Cost calculation (in USD cents for precision)
    input_cost_cents = sa.Column(sa.Numeric(10, 4), default=0)
    output_cost_cents = sa.Column(sa.Numeric(10, 4), default=0)
    total_cost_cents = sa.Column(sa.Numeric(10, 4), default=0)

    # Timing
    latency_ms = sa.Column(sa.Integer)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow, index=True)

    # Metadata
    metadata_json = sa.Column(sa.JSON, default={})


# Default cost per 1K tokens (in cents) - Update based on your Azure pricing
MODEL_COSTS = {
    "gpt-4": {"input": 3.0, "output": 6.0},
    "gpt-4-turbo": {"input": 1.0, "output": 3.0},
    "gpt-4o": {"input": 0.25, "output": 1.0},
    "gpt-4o-mini": {"input": 0.015, "output": 0.06},
    "gpt-35-turbo": {"input": 0.05, "output": 0.15},
    "text-embedding-ada-002": {"input": 0.01, "output": 0},
    "text-embedding-3-small": {"input": 0.002, "output": 0},
    "text-embedding-3-large": {"input": 0.013, "output": 0},
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int = 0) -> tuple[Decimal, Decimal, Decimal]:
    """
    Calculate costs based on token usage.

    Returns:
        Tuple of (input_cost, output_cost, total_cost) in cents
    """
    costs = MODEL_COSTS.get(model_name, {"input": 0, "output": 0})

    input_cost = Decimal(str(costs["input"])) * Decimal(input_tokens) / 1000
    output_cost = Decimal(str(costs["output"])) * Decimal(output_tokens) / 1000
    total_cost = input_cost + output_cost

    return input_cost, output_cost, total_cost


async def record_llm_cost(
    db,
    request_id: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int = 0,
    operation: str = "chat",
    thread_id: str | None = None,
    user_id: int | None = None,
    tenant_id: str | None = None,
    latency_ms: int | None = None,
    metadata: dict | None = None,
) -> LLMCostRecord:
    """
    Record an LLM API call with cost tracking.
    """
    input_cost, output_cost, total_cost = calculate_cost(model_name, input_tokens, output_tokens)

    record = LLMCostRecord(
        request_id=request_id,
        thread_id=thread_id,
        user_id=user_id,
        tenant_id=tenant_id,
        model_name=model_name,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_cost_cents=input_cost,
        output_cost_cents=output_cost,
        total_cost_cents=total_cost,
        latency_ms=latency_ms,
        metadata_json=metadata or {},
    )

    db.add(record)
    await db.commit()

    return record
