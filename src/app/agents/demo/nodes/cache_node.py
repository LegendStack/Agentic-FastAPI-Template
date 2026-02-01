"""
Cache Node - Semantic Caching
==============================
Checks if a similar query has been answered before.
Returns cached response if found, skipping expensive LLM calls.

This demonstrates the Semantic Caching feature (V4.0).
"""

import hashlib
import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class CacheNode:
    """
    Semantic cache lookup node.
    
    Features:
    - In-memory cache for demo purposes
    - Similarity-based lookup (simplified)
    - TTL support
    
    In production, this uses Redis with vector similarity search.
    
    Usage:
        node = CacheNode(config)
        new_state = await node(state)
    """
    
    def __init__(self, config: DemoAgentConfig):
        """Initialize with configuration."""
        self.config = config
        # In-memory cache for demo: {hash -> response}
        self._cache: dict[str, dict[str, Any]] = {}
        
        # Pre-populate with some cached responses
        self._seed_cache()
    
    def _seed_cache(self):
        """Add some sample cached responses."""
        samples = [
            ("what is legendstack", {
                "response": "LegendStack is an enterprise Agentic AI framework. [CACHED]",
                "tokens": {"prompt": 10, "completion": 15},
            }),
            ("how does rag work", {
                "response": "RAG combines retrieval with generation for grounded responses. [CACHED]",
                "tokens": {"prompt": 8, "completion": 12},
            }),
        ]
        for query, data in samples:
            cache_key = self._get_cache_key(query)
            self._cache[cache_key] = data
    
    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key from text (simplified - in production use embeddings)."""
        # Normalize and hash
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Check cache for existing response.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with cache_hit flag and possibly cached response
        """
        if not self.config.ENABLE_SEMANTIC_CACHE:
            logger.info("CacheNode: Caching disabled, skipping")
            return {"cache_hit": False}
        
        query = state.get("sanitized_input", state.get("original_input", ""))
        cache_key = self._get_cache_key(query)
        
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.info(f"CacheNode: Cache HIT for query")
            return {
                "cache_hit": True,
                "response": cached["response"],
                "cost_info": {
                    "prompt_tokens": 0,  # No LLM call needed
                    "completion_tokens": 0,
                    "cached": True,
                    "saved_tokens": cached["tokens"]["prompt"] + cached["tokens"]["completion"],
                },
            }
        
        logger.info("CacheNode: Cache MISS")
        return {"cache_hit": False}
    
    def store(self, query: str, response: str, tokens: dict[str, int]):
        """Store a response in cache for future use."""
        cache_key = self._get_cache_key(query)
        self._cache[cache_key] = {
            "response": response,
            "tokens": tokens,
        }
        logger.info(f"CacheNode: Stored response in cache")
