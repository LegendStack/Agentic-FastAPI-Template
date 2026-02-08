"""
Cost Node - Token Usage & Cost Tracking
========================================
Tracks token usage and estimates costs for LLM calls.
Enables quota management and usage analytics.

This demonstrates the Cost Tracking feature (V1.2).
"""

import logging
from datetime import datetime
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class CostNode:
    """
    Cost tracking node.

    Features:
    - Token usage aggregation
    - Cost estimation by model
    - Tenant-level tracking

    Usage:
        node = CostNode(config)
        new_state = await node(state)
    """

    # Cost per 1K tokens (USD) - approximate values
    MODEL_COSTS = {
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "mock-gpt-4o": {"input": 0.0, "output": 0.0},  # Free for mocks!
    }

    def __init__(self, config: DemoAgentConfig):
        """Initialize with configuration."""
        self.config = config
        # Usage tracking: {tenant_id -> {date -> usage}}
        self._usage: dict[str, dict[str, dict[str, Any]]] = {}

    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Track and aggregate costs.

        Args:
            state: Current agent state

        Returns:
            Updated state with cost information
        """
        if not self.config.ENABLE_COST_TRACKING:
            logger.info("CostNode: Cost tracking disabled, skipping")
            return {}

        cost_info = state.get("cost_info", {})
        tenant_id = state.get("tenant_id", "default")

        # Calculate cost
        prompt_tokens = cost_info.get("prompt_tokens", 0)
        completion_tokens = cost_info.get("completion_tokens", 0)
        model = cost_info.get("model", "mock-gpt-4o")
        was_cached = cost_info.get("cached", False)

        if was_cached:
            saved_tokens = cost_info.get("saved_tokens", 0)
            logger.info(f"CostNode: Cache hit - saved {saved_tokens} tokens!")
            cost_info["estimated_savings_usd"] = self._calculate_cost(model, saved_tokens // 2, saved_tokens // 2)
        else:
            cost_usd = self._calculate_cost(model, prompt_tokens, completion_tokens)
            cost_info["estimated_cost_usd"] = cost_usd

            # Track usage
            self._record_usage(tenant_id, prompt_tokens, completion_tokens, cost_usd)

            logger.info(f"CostNode: {prompt_tokens} + {completion_tokens} tokens = ${cost_usd:.6f}")

        return {"cost_info": cost_info}

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD."""
        costs = self.MODEL_COSTS.get(model, self.MODEL_COSTS["mock-gpt-4o"])
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return round(input_cost + output_cost, 6)

    def _record_usage(self, tenant_id: str, input_tokens: int, output_tokens: int, cost_usd: float):
        """Record usage for analytics."""
        today = datetime.now().strftime("%Y-%m-%d")

        if tenant_id not in self._usage:
            self._usage[tenant_id] = {}

        if today not in self._usage[tenant_id]:
            self._usage[tenant_id][today] = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": 0.0,
                "request_count": 0,
            }

        self._usage[tenant_id][today]["total_input_tokens"] += input_tokens
        self._usage[tenant_id][today]["total_output_tokens"] += output_tokens
        self._usage[tenant_id][today]["total_cost_usd"] += cost_usd
        self._usage[tenant_id][today]["request_count"] += 1

    def get_usage(self, tenant_id: str, date: str | None = None) -> dict[str, Any]:
        """Get usage statistics for a tenant."""
        if date:
            return self._usage.get(tenant_id, {}).get(date, {})
        return self._usage.get(tenant_id, {})

    def get_total_cost(self, tenant_id: str) -> float:
        """Get total cost for a tenant across all time."""
        tenant_usage = self._usage.get(tenant_id, {})
        return sum(day["total_cost_usd"] for day in tenant_usage.values())
