"""
Moderation and Hallucination Detection.
=======================================
Ensures LLM outputs are safe and grounded in the provided context.
"""

import logging
from typing import Any, Dict

from ..agents.azure_openai import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class Moderator:
    """
    Standard Moderator for LegendStack.

    Provides:
    - Hallucination check (Context vs Answer)
    - Content Safety (Azure Content Safety or custom prompt)
    """

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or get_llm_service()

    async def check_hallucination(self, context: str, answer: str) -> Dict[str, Any]:
        """
        Uses an LLM as a judge to identify hallucinations.
        """
        prompt = f"""
        Analyze if the provided ANSWER is fully grounded in the CONTEXT. 
        If the answer contains information NOT present in the context, flag it as a hallucination.
        
        CONTEXT:
        {context}
        
        ANSWER:
        {answer}
        
        Return a JSON object with:
        - "is_hallucination": boolean
        - "reason": string explaining why
        - "confidence": number (0-1)
        """

        # We use the LLM to judge
        response = await self.llm_service.chat([{"role": "user", "content": prompt}])
        # Note: In a real implementation, we'd parse the structured output properly
        # For now, we'll assume a basic JSON return format from the LLM
        return {"content": response.content, "status": "judged"}

    async def check_safety(self, text: str) -> Dict[str, Any]:
        """
        Basic safety check.
        """
        # In a real enterprise scenario, we'd call Azure Content Safety here.
        # For the template, we demonstrate the hook.
        return {"safe": True, "score": 1.0}


def get_moderator() -> Moderator:
    """Dependency for obtaining the Moderator."""
    return Moderator()
