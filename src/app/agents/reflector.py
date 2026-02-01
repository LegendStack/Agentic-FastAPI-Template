"""
Reflector Pattern.
=================
Provides agents with the ability to critique their own outputs using the EvalEngine.
"""

import logging
from typing import Any, Dict, List

from ..eval.engine import EvalEngine
from ..guardrails.moderation import Moderator

logger = logging.getLogger(__name__)


class Reflector:
    """
    Standard Reflector for LegendStack agents.

    Workflow:
    1. Receive a draft response and context.
    2. Use EvalEngine to get scores (Faithfulness, Relevancy).
    3. If scores are below threshold, generate 'Self-Feedback'.
    4. Return feedback to the agent for a second pass.
    """

    def __init__(
        self,
        eval_engine: EvalEngine | None = None,
        moderator: Moderator | None = None,
        threshold: float = 0.8,
    ):
        self.eval_engine = eval_engine or EvalEngine()
        self.moderator = moderator or Moderator()
        self.threshold = threshold

    async def reflect(
        self, question: str, response: str, contexts: List[str], ground_truth: str | None = None
    ) -> Dict[str, Any]:
        """
        Analyzes a response and returns a critique.
        """
        logger.info("Starting self-reflection loop...")

        # 1. Modular Evaluation
        eval_results = await self.eval_engine.run_eval(
            questions=[question],
            answers=[response],
            contexts=[contexts],
            ground_truths=[ground_truth] if ground_truth else None,
        )

        metrics = eval_results[0]
        faithfulness = metrics.get("faithfulness", 1.0)
        relevancy = metrics.get("answer_relevancy", 1.0)

        # 2. Moderation check
        safety = await self.moderator.check_safety(response)
        hallucination = await self.moderator.check_hallucination("\n".join(contexts), response)

        # 3. Decision logic
        needs_revision = False
        feedback = []

        if faithfulness < self.threshold:
            needs_revision = True
            feedback.append(
                f"Faithfulness score is too low ({faithfulness:.2f}). Please ensure all claims are grounded in context."
            )

        if relevancy < self.threshold:
            needs_revision = True
            feedback.append(
                f"Answer relevancy is too low ({relevancy:.2f}). Please address the question more directly."
            )

        if not safety["safe"]:
            needs_revision = True
            feedback.append("The response triggered a safety guardrail. Please refine the content.")

        return {"needs_revision": needs_revision, "feedback": "\n".join(feedback), "scores": metrics, "safety": safety}
