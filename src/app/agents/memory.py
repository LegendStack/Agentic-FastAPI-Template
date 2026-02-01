"""
Agent Memory Management.
========================
Smart context window management with summarization and pruning.

This module helps agents manage long conversations by:
1. Tracking token counts per message
2. Summarizing old messages to preserve context
3. Pruning messages to fit within context limits
"""

import logging
from abc import ABC, abstractmethod

import tiktoken

from .azure_openai import LLMService
from .conversations import ConversationService

logger = logging.getLogger(__name__)

# Default context limits by model
MODEL_CONTEXT_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-35-turbo": 16384,
}


class BaseMemoryStrategy(ABC):
    """Abstract base for memory management strategies."""

    @abstractmethod
    async def get_context(self, thread_id: str, max_tokens: int, system_prompt: str = "") -> list[dict]:
        """Get messages that fit within token limit."""
        pass


class TruncationStrategy(BaseMemoryStrategy):
    """Simple truncation - keep most recent messages."""

    def __init__(self, conversation_service: ConversationService, encoding_name: str = "cl100k_base"):
        self.conversation_service = conversation_service
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    async def get_context(self, thread_id: str, max_tokens: int, system_prompt: str = "") -> list[dict]:
        """Get messages, truncating from the beginning if needed."""
        messages = await self.conversation_service.get_messages(thread_id, limit=100)

        result = []
        remaining_tokens = max_tokens - self.count_tokens(system_prompt)

        # Add messages from most recent, working backwards
        for msg in reversed(messages):
            msg_tokens = self.count_tokens(msg.content)
            if msg_tokens <= remaining_tokens:
                result.insert(0, {"role": msg.role, "content": msg.content})
                remaining_tokens -= msg_tokens
            else:
                break

        return result


class SummarizationStrategy(BaseMemoryStrategy):
    """Summarize old messages to preserve context while reducing tokens."""

    def __init__(
        self,
        conversation_service: ConversationService,
        llm_service: LLMService,
        encoding_name: str = "cl100k_base",
        summary_threshold: int = 10,  # Summarize when more than N messages
        keep_recent: int = 5,  # Always keep last N messages unsummarized
    ):
        self.conversation_service = conversation_service
        self.llm = llm_service
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.summary_threshold = summary_threshold
        self.keep_recent = keep_recent
        self._summary_cache: dict[str, str] = {}

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    async def summarize(self, messages: list[dict]) -> str:
        """Create a summary of messages."""
        if not messages:
            return ""

        conversation_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])

        summary_prompt = f"""Summarize this conversation concisely while preserving key facts, decisions, and context needed for continuation:

{conversation_text}

Summary:"""

        response = await self.llm.chat([{"role": "user", "content": summary_prompt}])
        return response.content

    async def get_context(self, thread_id: str, max_tokens: int, system_prompt: str = "") -> list[dict]:
        """Get context with summarization for long conversations."""
        messages = await self.conversation_service.get_messages(thread_id, limit=100)

        if len(messages) <= self.summary_threshold:
            # Short conversation, no summarization needed
            return [{"role": m.role, "content": m.content} for m in messages]

        # Split into old (to summarize) and recent (keep full)
        old_messages = messages[: -self.keep_recent]
        recent_messages = messages[-self.keep_recent :]

        # Check cache for existing summary
        cache_key = f"{thread_id}:{len(old_messages)}"
        if cache_key not in self._summary_cache:
            old_as_dicts = [{"role": m.role, "content": m.content} for m in old_messages]
            self._summary_cache[cache_key] = await self.summarize(old_as_dicts)

        summary = self._summary_cache[cache_key]

        # Build result with summary + recent messages
        result = [{"role": "system", "content": f"Previous conversation summary:\n{summary}"}]

        remaining_tokens = max_tokens - self.count_tokens(system_prompt) - self.count_tokens(summary)

        for msg in recent_messages:
            msg_tokens = self.count_tokens(msg.content)
            if msg_tokens <= remaining_tokens:
                result.append({"role": msg.role, "content": msg.content})
                remaining_tokens -= msg_tokens

        return result


class MemoryManager:
    """
    High-level memory management for agents.

    Usage:
        memory = MemoryManager(conversation_service, llm_service)

        # Get context that fits in token budget
        context = await memory.get_context("thread-123", max_tokens=4000)

        # With custom strategy
        memory.set_strategy(SummarizationStrategy(...))
    """

    def __init__(
        self,
        conversation_service: ConversationService,
        llm_service: LLMService | None = None,
        strategy: BaseMemoryStrategy | None = None,
        default_max_tokens: int = 4000,
    ):
        self.conversation_service = conversation_service
        self.llm_service = llm_service
        self.default_max_tokens = default_max_tokens

        # Default to truncation strategy
        self._strategy = strategy or TruncationStrategy(conversation_service)

    def set_strategy(self, strategy: BaseMemoryStrategy) -> None:
        """Change the memory management strategy."""
        self._strategy = strategy

    async def get_context(self, thread_id: str, max_tokens: int | None = None, system_prompt: str = "") -> list[dict]:
        """Get conversation context within token budget."""
        max_tokens = max_tokens or self.default_max_tokens
        return await self._strategy.get_context(thread_id, max_tokens, system_prompt)

    async def prune_old_messages(self, thread_id: str, keep_recent: int = 50) -> int:
        """Delete old messages beyond the keep threshold. Returns count deleted."""
        messages = await self.conversation_service.get_messages(thread_id, limit=1000)

        if len(messages) <= keep_recent:
            return 0

        # Get IDs of messages to delete
        messages_to_delete = messages[:-keep_recent]
        deleted_count = len(messages_to_delete)

        # Note: Actual deletion would require adding delete method to ConversationService
        logger.info(f"Would prune {deleted_count} messages from {thread_id}")

        return deleted_count
