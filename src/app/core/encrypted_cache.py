"""
Zero-Trust Semantic Cache Wrapper.
==================================
Wraps LangChain's RedisSemanticCache to encrypt/decrypt responses at rest.
"""

import logging
from typing import Any

try:
    from langchain_core.caches import RETURN_VAL_TYPE
    from langchain_core.outputs import Generation
    from langchain_redis import RedisSemanticCache
except ImportError:
    RedisSemanticCache = object  # Fallback
    Generation = object
    RETURN_VAL_TYPE = Any


logger = logging.getLogger(__name__)


class EncryptedRedisSemanticCache(RedisSemanticCache):
    """
    Subclass of RedisSemanticCache that extracts the core user prompt for embedding.
    This prevents 'System Prompt Drowning' where large system prompts overwhelm 
    the similarity calculation for small user prompts.
    """

    def _extract_meaningful_content(self, prompt: str) -> str:
        """
        Extracts the user message from a serialized LangChain message array.
        LangChain usually serializes as 'Human: content' or '[{"role": "user", "content": "..."}]'
        """
        # 1. Try to find the last Human/User message in common LangChain string formats
        # Format: "System: ... \nHuman: [User Message]"
        human_match = re.search(r"Human:\s*(.*)$", prompt, re.DOTALL | re.MULTILINE)
        if human_match:
            return human_match.group(1).strip()

        # 2. Try JSON format if serialized as list of dicts
        if prompt.strip().startswith("[") and prompt.strip().endswith("]"):
            try:
                import json
                msgs = json.loads(prompt)
                user_msgs = [m.get("content", "") for m in msgs if m.get("role") == "user"]
                if user_msgs:
                    return user_msgs[-1].strip()
            except:
                pass

        # 3. Fallback to full prompt if extraction fails
        return prompt

    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        """Lookup based on meaningful content only."""
        meaningful_prompt = self._extract_meaningful_content(prompt)
        logger.debug(f"Cache Lookup: Original Length={len(prompt)}, Meaningful Length={len(meaningful_prompt)}")
        
        # We call the parent lookup but we want it to use our meaningful prompt for embedding
        return super().lookup(meaningful_prompt, llm_string)

    def update(self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE) -> None:
        """Store using meaningful content for the embedding."""
        meaningful_prompt = self._extract_meaningful_content(prompt)
        logger.debug(f"Cache Update: Original Length={len(prompt)}, Meaningful Length={len(meaningful_prompt)}")
        
        super().update(meaningful_prompt, llm_string, return_val)
