"""
Refine Node
===========
Handle conversational refinement based on user feedback.
Updates the decomposition based on user's requests.
"""

import logging
from typing import Any

from ...azure_openai import LLMService, get_llm_service
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
                usage = {}
            else:
                result, usage = await self._llm_refine(
                    current_result, 
                    feedback, 
                    edit_context=state.get("edit_context") or "",
                    enriched_context=state.get("enriched_context") or "",
                    story_template=state.get("story_template", self.config.STORY_TEMPLATE)
                )

            logger.info(f"RefineNode: Updated to {len(result.stories)} stories")

            return {
                "stories": result.stories,
                "current_result": result,
                "usage_metadata": usage,
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

        # Try to find a target story ID in the feedback
        target_story = None
        target_index = -1
        
        # Simple heuristic: look for "story-XXX" or just "story X"
        import re
        id_match = re.search(r"story-?(\d+)", feedback_lower)
        if id_match:
            suffix = id_match.group(1).zfill(3)
            search_id = f"STORY-{suffix}"
            for i, s in enumerate(stories):
                if s.id == search_id:
                    target_story = s
                    target_index = i
                    break
        
        # Fallback: if no ID found, use last story
        if not target_story and stories:
            target_story = stories[-1]
            target_index = len(stories) - 1

        # Simulate common refinement operations
        if "edge case" in feedback_lower or "edge cases" in feedback_lower:
            # Add edge cases to target story (or all if generic)
            targets = [target_story] if target_story and "all" not in feedback_lower else stories
            for story in targets:
                if len(story.edge_cases) < 3:
                    story.edge_cases.append("Handle timeout scenario")
                    story.edge_cases.append("Handle concurrent access")

        elif "split" in feedback_lower and target_story:
            # Split the target story
            original = target_story
            new_id_1 = f"{original.id}-A"
            new_id_2 = f"{original.id}-B"
            
            part1 = UserStory(
                id=new_id_1,
                title=f"{original.title} - Part 1",
                description=f"First part of {original.title}.",
                acceptance_criteria=original.acceptance_criteria[:1],
                estimated_complexity="S",
                tags=original.tags,
            )
            part2 = UserStory(
                id=new_id_2,
                title=f"{original.title} - Part 2",
                description=f"Second part of {original.title}.",
                acceptance_criteria=original.acceptance_criteria[1:] if len(original.acceptance_criteria) > 1 else [AcceptanceCriteria(description="Additional criteria")],
                estimated_complexity="S",
                tags=original.tags,
            )
            # Remove original and insert new ones
            stories.pop(target_index)
            stories.insert(target_index, part2)
            stories.insert(target_index, part1)

        elif "merge" in feedback_lower:
            # Merge last two stories (simplification for mock)
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
            if target_story:
                target_story.technical_notes.append(f"Refined based on: {feedback[:100]}")

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
        edit_context: str = "",
        enriched_context: str = "",
        story_template: str = "standard",
    ) -> tuple[DecompositionResult, dict[str, Any]]:
        """Use LLM to refine the decomposition."""
        if not self.llm_service:
            self.llm_service = get_llm_service()

        # Build prompts
        current_json = current_result.model_dump_json(indent=2)
        project_key = current_result.epic.project_key if current_result.epic else None
        
        # Combine contexts
        full_context = ""
        if edit_context:
            full_context += f"Context from Manual Edits:\n{edit_context}\n\n"
        if enriched_context:
            full_context += f"Context from Jira:\n{enriched_context}\n\n"

        system_prompt = get_refine_system_prompt(current_json, story_template=story_template, project_key=project_key)
        user_prompt = get_refine_user_prompt(feedback, edit_context=full_context.strip())

        # Use structured output validator with retry
        result_data, usage_metadata = await self.validator.with_retry(
            llm=self.llm_service,
            prompt=user_prompt,
            schema=DecompositionResult,
            max_retries=self.config.MAX_RETRIES,
            system_prompt=system_prompt,
        )

        # Preserve the original epic
        result_data.epic = current_result.epic

        return result_data, usage_metadata


# Convenience function for standalone testing
async def refine_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for RefineNode."""
    node = RefineNode(config=config)
    return await node(state)
