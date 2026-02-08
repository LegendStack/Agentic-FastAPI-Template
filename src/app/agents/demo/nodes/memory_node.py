"""
Memory Node - Conversation Summarization
=========================================
Manages long-term conversation memory using summarization.
Keeps context within token budgets while preserving important information.

This demonstrates the Memory Management feature (V2.0).
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class MemoryNode:
    """
    Memory management node with summarization.

    Features:
    - Conversation history tracking
    - Automatic summarization for long conversations
    - Token budget management

    Usage:
        node = MemoryNode(config)
        new_state = await node(state)
    """

    MAX_MESSAGES_BEFORE_SUMMARIZATION = 10

    def __init__(self, config: DemoAgentConfig):
        """Initialize with configuration."""
        self.config = config
        # In-memory conversation summaries: {thread_id -> summary}
        self._summaries: dict[str, str] = {}

    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Process memory and summarization.

        Args:
            state: Current agent state

        Returns:
            Updated state with memory context
        """
        if not self.config.ENABLE_MEMORY_SUMMARIZATION:
            logger.info("MemoryNode: Summarization disabled, skipping")
            return {}

        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("MemoryNode: Skipping due to cache hit")
            return {}

        thread_id = state.get("thread_id", "default")
        messages = state.get("messages", [])
        current_context = state.get("context", "")

        logger.info(f"MemoryNode: Processing memory for thread {thread_id}")

        # Check if we have a summary for this thread
        if thread_id in self._summaries:
            memory_context = f"\n\n📝 Previous Conversation Summary:\n{self._summaries[thread_id]}"
            enriched_context = current_context + memory_context
            logger.info("MemoryNode: Added existing summary to context")
            return {"context": enriched_context}

        # Check if messages need summarization
        if len(messages) > self.MAX_MESSAGES_BEFORE_SUMMARIZATION:
            # In production, this would call an LLM to summarize
            # For demo, we create a simple summary
            summary = self._create_simple_summary(messages)
            self._summaries[thread_id] = summary
            logger.info("MemoryNode: Created new summary for long conversation")

        return {}

    def _create_simple_summary(self, messages: list[dict[str, Any]]) -> str:
        """Create a simple summary of messages (mock implementation)."""
        topics = []
        for msg in messages:
            content = msg.get("content", "").lower()
            if "help" in content:
                topics.append("requesting assistance")
            if "legendstack" in content:
                topics.append("discussing LegendStack framework")
            if "rag" in content or "retrieval" in content:
                topics.append("exploring RAG capabilities")

        if topics:
            return f"User has been {', '.join(set(topics))}."
        return "General conversation about AI and development."

    def store_summary(self, thread_id: str, summary: str):
        """Manually store a summary for a thread."""
        self._summaries[thread_id] = summary

    def get_summary(self, thread_id: str) -> str | None:
        """Get the summary for a thread."""
        return self._summaries.get(thread_id)
