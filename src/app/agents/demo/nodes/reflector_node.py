"""
Reflector Node - Self-Correction
=================================
Evaluates response quality and triggers regeneration if needed.
Uses evaluation metrics to decide if the response is "good enough".

This demonstrates the Self-Correction / Reflector feature (V4.0).
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class ReflectorNode:
    """
    Self-correction node using evaluation.

    Features:
    - Quality scoring (simplified for demo)
    - Critique generation
    - Regeneration triggering

    In production, this uses the EvalEngine with RAGAS metrics.

    Usage:
        node = ReflectorNode(config)
        result = await node(state)
    """

    # Quality indicators (simplified scoring)
    QUALITY_KEYWORDS_POSITIVE = [
        "because",
        "therefore",
        "specifically",
        "for example",
        "based on",
        "according to",
        "the context shows",
    ]

    QUALITY_KEYWORDS_NEGATIVE = ["i don't know", "i'm not sure", "i cannot", "unclear", "no information", "apologize"]

    def __init__(self, config: DemoAgentConfig):
        """Initialize with configuration."""
        self.config = config
        self.reflection_count = 0
        self.max_reflections = 2  # Prevent infinite loops

    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Evaluate response quality and decide on reflection.

        Args:
            state: Current agent state

        Returns:
            Updated state with reflection info
        """
        if not self.config.ENABLE_REFLECTOR:
            logger.info("ReflectorNode: Reflector disabled, skipping")
            return {"reflection": None}

        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("ReflectorNode: Skipping due to cache hit")
            return {}

        response = state.get("response", "")
        context = state.get("context", "")

        logger.info("ReflectorNode: Evaluating response quality")

        # Calculate quality score
        score = self._calculate_quality_score(response, context)
        logger.info(f"ReflectorNode: Quality score = {score:.2f}")

        # Check if reflection needed
        if score < self.config.REFLECTOR_THRESHOLD and self.reflection_count < self.max_reflections:
            self.reflection_count += 1
            critique = self._generate_critique(response, score)

            logger.info(f"ReflectorNode: Reflection needed (attempt {self.reflection_count})")

            return {
                "reflection": {
                    "needed": True,
                    "score": score,
                    "critique": critique,
                    "attempt": self.reflection_count,
                },
            }

        # Reset counter for next conversation
        self.reflection_count = 0

        return {
            "reflection": {
                "needed": False,
                "score": score,
                "critique": None,
            },
        }

    def _calculate_quality_score(self, response: str, context: str) -> float:
        """
        Calculate a quality score for the response.

        In production, this uses RAGAS metrics (faithfulness, relevancy).
        This is a simplified heuristic version.
        """
        response_lower = response.lower()

        # Start with base score
        score = 0.5

        # Positive indicators
        for keyword in self.QUALITY_KEYWORDS_POSITIVE:
            if keyword in response_lower:
                score += 0.1

        # Negative indicators
        for keyword in self.QUALITY_KEYWORDS_NEGATIVE:
            if keyword in response_lower:
                score -= 0.15

        # Check if response references context
        if context:
            context_words = set(context.lower().split())
            response_words = set(response_lower.split())
            overlap = len(context_words & response_words)
            if overlap > 5:
                score += 0.1

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _generate_critique(self, response: str, score: float) -> str:
        """Generate a critique for low-quality responses."""
        critiques = []
        response_lower = response.lower()

        if "i don't know" in response_lower or "i'm not sure" in response_lower:
            critiques.append(
                "The response indicates uncertainty. Try to extract more specific information from the context."
            )

        if len(response.split()) < 20:
            critiques.append("The response is too brief. Provide more detailed explanation.")

        if score < 0.4:
            critiques.append("The response lacks grounding in the provided context. Reference specific information.")

        if not critiques:
            critiques.append("General improvement needed: be more specific and reference the context directly.")

        return " ".join(critiques)
