"""
Output Node - Response Formatting & Caching
============================================
Final node in the pipeline. Handles:
- Response formatting
- Cache storage
- Final state preparation

This is the last step before returning to the user.
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class OutputNode:
    """
    Output formatting node.
    
    Features:
    - Response cleanup
    - Cache storage for future queries
    - Final metadata assembly
    
    Usage:
        node = OutputNode(config, cache_node)
        new_state = await node(state)
    """
    
    def __init__(self, config: DemoAgentConfig, cache_node=None):
        """Initialize with dependencies."""
        self.config = config
        self.cache_node = cache_node  # Reference to cache node for storing
    
    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Format and finalize the response.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with final response
        """
        response = state.get("response", "")
        original_input = state.get("original_input", "")
        cost_info = state.get("cost_info", {})
        
        logger.info("OutputNode: Formatting final response")
        
        # Add response to messages
        messages = state.get("messages", []).copy()
        messages.append({
            "role": "assistant",
            "content": response,
        })
        
        # Store in cache if not already cached
        if not state.get("cache_hit", False) and self.cache_node:
            tokens = {
                "prompt": cost_info.get("prompt_tokens", 0),
                "completion": cost_info.get("completion_tokens", 0),
            }
            self.cache_node.store(original_input, response, tokens)
        
        # Prepare final metadata
        metadata = state.get("metadata", {})
        metadata["processing_complete"] = True
        metadata["features_used"] = self._get_features_used(state)
        
        logger.info(f"OutputNode: Response ready ({len(response)} chars)")
        
        return {
            "messages": messages,
            "metadata": metadata,
        }
    
    def _get_features_used(self, state: DemoAgentState) -> list[str]:
        """Summarize which features were used in this request."""
        features = []
        
        if state.get("cache_hit"):
            features.append("semantic_cache")
        
        if state.get("context"):
            features.append("rag_retrieval")
        
        if "📊 Knowledge Graph" in state.get("context", ""):
            features.append("graph_rag")
        
        if "🧠 Entity Memory" in state.get("context", ""):
            features.append("entity_memory")
        
        if state.get("entities"):
            features.append("entity_extraction")
        
        reflection = state.get("reflection")
        if reflection and reflection.get("needed"):
            features.append("self_correction")
        
        if state.get("needs_human_approval"):
            features.append("hitl")
        
        if state.get("cost_info", {}).get("estimated_cost_usd"):
            features.append("cost_tracking")
        
        metadata = state.get("metadata", {})
        if metadata.get("pii_detected"):
            features.append("pii_masking")
        
        if metadata.get("moderation_passed") is not None:
            features.append("content_moderation")
        
        return features
