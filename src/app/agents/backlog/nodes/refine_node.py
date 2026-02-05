"""
Refine Node
===========
Handle conversational refinement based on user feedback.
Updates the decomposition based on user's requests.
"""

import logging
from typing import Any

from ...azure_openai import LLMService
from ...structured_output import StructuredOutputValidator
from ..config import BacklogAgentConfig
from ..prompts import get_refine_system_prompt, get_refine_user_prompt
from ..schemas import AcceptanceCriteria, DecompositionResult, UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class RefineNode:
    """
    Refine decomposition based on user feedback.

    Interprets user's requests and updates stories accordingly.
    Supports operations like:
    - Adding more edge cases
    - Splitting stories
    - Merging stories
    - Adding/removing acceptance criteria
    - Adjusting complexity estimates

    Usage:
        node = RefineNode(config=BacklogAgentConfig())
        updated_state = await node(state)
    """

    def __init__(
        self,
        config: BacklogAgentConfig | None = None,
        llm_service: LLMService | None = None,
    ):
        self.config = config or BacklogAgentConfig()
        self.llm_service = llm_service
        self.validator = StructuredOutputValidator()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Refine the decomposition based on feedback.

        Args:
            state: Current agent state with stories and refinement_feedback

        Returns:
            State update with modified stories
        """
        logger.info("RefineNode: Processing refinement request")

        feedback = state.get("refinement_feedback")
        current_result = state.get("current_result")

        if not feedback:
            return {"error": "No feedback provided for refinement"}

        if not current_result:
            return {"error": "No existing decomposition to refine"}

        # Convert from dict if needed
        if isinstance(current_result, dict):
            current_result = DecompositionResult.model_validate(current_result)

        try:
            if self.config.USE_MOCKS:
                result = await self._mock_refine(current_result, feedback)
            else:
                result = await self._llm_refine(current_result, feedback)

            logger.info(f"RefineNode: Updated to {len(result.stories)} stories")

            return {
                "stories": result.stories,
                "current_result": result,
                "refinement_feedback": None,  # Clear feedback after processing
                "error": None,
            }

        except Exception as e:
            logger.error(f"RefineNode: Error - {e}")
            return {"error": f"Refinement failed: {str(e)}"}

    async def _mock_refine(
        self,
        current_result: DecompositionResult,
        feedback: str,
    ) -> DecompositionResult:
        """Apply mock refinements for testing."""
        logger.info("RefineNode: Using mock refinement")

        feedback_lower = feedback.lower()
        stories = list(current_result.stories)

        # Simulate common refinement operations
        if "edge case" in feedback_lower or "edge cases" in feedback_lower:
            # Add edge cases to all stories
            for story in stories:
                if len(story.edge_cases) < 3:
                    story.edge_cases.append("Handle timeout scenario")
                    story.edge_cases.append("Handle concurrent access")

        elif "split" in feedback_lower:
            # Split the last story into two
            if stories:
                original = stories[-1]
                new_id = f"STORY-{len(stories) + 1:03d}"
                new_story = UserStory(
                    id=new_id,
                    title=f"{original.title} - Part 2",
                    description=f"As a continuation of {original.id}, this covers additional aspects.",
                    acceptance_criteria=[
                        AcceptanceCriteria(description="Additional functionality works"),
                        AcceptanceCriteria(description="Integration with Part 1 is seamless"),
                    ],
                    dependencies=[original.id],
                    estimated_complexity="S",
                    tags=original.tags,
                )
                stories.append(new_story)

        elif "merge" in feedback_lower:
            # Merge last two stories
            if len(stories) >= 2:
                story1 = stories[-2]
                story2 = stories[-1]
                merged = UserStory(
                    id=story1.id,
                    title=f"{story1.title} (Combined)",
                    description=f"{story1.description}\n\nAdditionally: {story2.description}",
                    acceptance_criteria=story1.acceptance_criteria + story2.acceptance_criteria,
                    edge_cases=story1.edge_cases + story2.edge_cases,
                    technical_notes=story1.technical_notes + story2.technical_notes,
                    dependencies=[d for d in story1.dependencies if d != story2.id],
                    estimated_complexity="L",
                    tags=list(set(story1.tags + story2.tags)),
                )
                stories = stories[:-2] + [merged]

        elif "add" in feedback_lower and "story" in feedback_lower:
            # Add a new story
            new_id = f"STORY-{len(stories) + 1:03d}"
            new_story = UserStory(
                id=new_id,
                title="Additional Story (from feedback)",
                description="As a user, I want this additional capability based on feedback.",
                acceptance_criteria=[
                    AcceptanceCriteria(description="New functionality is implemented"),
                    AcceptanceCriteria(description="Existing features remain unaffected"),
                ],
                estimated_complexity="M",
                tags=["feedback", "enhancement"],
            )
            stories.append(new_story)

        else:
            # Generic refinement - just add a note
            logger.info(f"RefineNode: Generic refinement applied for: {feedback[:50]}")
            if stories:
                stories[0].technical_notes.append(f"Refined based on: {feedback[:100]}")

        return DecompositionResult(
            epic=current_result.epic,
            stories=stories,
            summary=f"Refined decomposition based on feedback. Now contains {len(stories)} stories.",
            recommendations=current_result.recommendations + ["Review changes from latest refinement"],
        )

    async def _llm_refine(
        self,
        current_result: DecompositionResult,
        feedback: str,
    ) -> DecompositionResult:
        """Use LLM to refine the decomposition."""
        if not self.llm_service:
            self.llm_service = LLMService()

        # Build prompts
        current_json = current_result.model_dump_json(indent=2)
        project_key = current_result.epic.project_key if current_result.epic else None
        system_prompt = get_refine_system_prompt(current_json, project_key=project_key)
        user_prompt = get_refine_user_prompt(feedback)

        # Use structured output validator with retry
        result = await self.validator.with_retry(
            llm=self.llm_service,
            prompt=user_prompt,
            schema=DecompositionResult,
            max_retries=self.config.MAX_RETRIES,
            system_prompt=system_prompt,
        )

        # Preserve the original epic
        result.epic = current_result.epic

        return result


# Convenience function for standalone testing
async def refine_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for RefineNode."""
    node = RefineNode(config=config)
    return await node(state)
