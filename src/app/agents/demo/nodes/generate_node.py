"""
Generate Node - LLM Response Generation
========================================
The core generation node that calls the LLM to produce responses.
Includes resilience patterns (retry, circuit breaker).

This demonstrates LLM integration and Resilience features.
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..mocks import MockLLM
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class GenerateNode:
    """
    LLM generation node with resilience.

    Features:
    - Context-aware prompt construction
    - Retry logic for transient failures
    - Token usage tracking

    Usage:
        node = GenerateNode(config, llm)
        new_state = await node(state)
    """

    SYSTEM_PROMPT = """You are a helpful AI assistant powered by LegendStack.
You provide accurate, grounded responses based on the provided context.
If you don't have enough information, say so clearly.

Available Context:
{context}
"""

    def __init__(self, config: DemoAgentConfig, llm: MockLLM | Any):
        """Initialize with dependencies."""
        self.config = config
        self.llm = llm

    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Generate response using the LLM.

        Args:
            state: Current agent state

        Returns:
            Updated state with generated response
        """
        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("GenerateNode: Skipping due to cache hit")
            return {}

        query = state.get("sanitized_input", state.get("original_input", ""))
        context = state.get("context", "No specific context available.")

        logger.info("GenerateNode: Generating response")

        # Build prompt
        system_prompt = self.SYSTEM_PROMPT.format(context=context)
        full_prompt = f"{system_prompt}\n\nUser Question: {query}"

        # Call LLM with retry logic
        max_retries = self.config.MAX_RETRIES if self.config.ENABLE_RETRY else 1
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.llm.ainvoke(full_prompt)

                logger.info(f"GenerateNode: Generated response ({response.completion_tokens} tokens)")

                return {
                    "response": response.content,
                    "cost_info": {
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                        "total_tokens": response.total_tokens,
                        "model": response.model,
                        "cached": False,
                    },
                }

            except Exception as e:
                last_error = e
                logger.warning(f"GenerateNode: Attempt {attempt + 1} failed - {e}")

                if not self.config.ENABLE_RETRY or attempt == max_retries - 1:
                    break

        # All retries failed
        logger.error(f"GenerateNode: All attempts failed - {last_error}")
        return {
            "response": "I apologize, but I'm temporarily unable to generate a response. Please try again.",
            "cost_info": {"error": str(last_error)},
        }
