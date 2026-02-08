"""
Critic Node
===========
Evaluates generated stories against quality criteria (INVEST).
"""

import logging
from typing import Any

from ...azure_openai import get_llm_service
from ..config import BacklogAgentConfig
from ..schemas import UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class CriticNode:
    """
    Quality control node that reviews stories.

    Checks for:
    - INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
    - Clarity of Acceptance Criteria
    - Missing Edge Cases
    """

    def __init__(self, config: BacklogAgentConfig | None = None):
        self.config = config or BacklogAgentConfig()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Critique stories and attach warnings if quality is low.
        """
        logger.info("CriticNode: Reviewing stories")

        current_result = state.get("current_result")
        if not current_result or not current_result.stories:
            return {}

        # Use LLM Service
        llm = get_llm_service()

        updated_stories = []
        for story in current_result.stories:
            try:
                critique = await self._evaluate_story(llm, story)

                # If score is low, attach warning to metadata/tech notes
                if critique["score"] < 4:
                    warning = f"⚠️ Quality Warning (Score: {critique['score']}/5): {critique['feedback']}"
                    # Append to technical notes so user sees it
                    if not story.technical_notes:
                        story.technical_notes = []
                    story.technical_notes.append(warning)

                updated_stories.append(story)
            except Exception as e:
                logger.error(f"CriticNode: Failed to critique {story.id} - {e}")
                updated_stories.append(story)

        return {"stories": updated_stories, "current_result": current_result}

    async def _evaluate_story(self, llm: Any, story: UserStory) -> dict[str, Any]:
        """Evaluate a single story against INVEST."""

        prompt = f"""You are a Senior Product Owner. Evaluate this User Story against the INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable).
        
        Story: {story.title}
        Description: {story.description}
        Acceptance Criteria: {len(story.acceptance_criteria)} items
        
        Task:
        1. Rate from 1-5 (5 is perfect).
        2. Provide a 1-sentence critique if score < 5.
        
        Output format:
        Score: [1-5]
        Feedback: [Your critique]
        """

        response = await llm.chat([{"role": "user", "content": prompt}])
        content = response.content.strip()

        # simple parsing
        score = 5
        feedback = "Good"

        try:
            lines = content.split("\n")
            for line in lines:
                if line.lower().startswith("score:"):
                    score_text = line.split(":")[1].strip()
                    # Hande "4/5" format
                    score = int(score_text.split("/")[0])
                elif line.lower().startswith("feedback:"):
                    feedback = line.split(":")[1].strip()
        except Exception:
            logger.warning(f"CriticNode: Failed to parse LLM response: {content}")

        return {"score": score, "feedback": feedback}
