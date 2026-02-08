"""
Story Enhancement Node
=====================
Targeted single-story enhancement with specific improvement types.
Allows users to enhance individual stories with acceptance criteria,
edge cases, BDD scenarios, or technical notes.
"""

import logging
import re
from enum import Enum
from typing import Any

from ...azure_openai import LLMService, get_llm_service
from ...structured_output import StructuredOutputValidator
from ..config import BacklogAgentConfig
from ..schemas import AcceptanceCriteria, DecompositionResult, UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class EnhancementType(str, Enum):
    """Types of story enhancements available."""

    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    EDGE_CASES = "edge_cases"
    BDD_SCENARIOS = "bdd"
    TECHNICAL_NOTES = "technical_notes"
    DEPENDENCIES = "dependencies"
    COMPLEXITY = "complexity"
    FULL = "full"  # All enhancements


# Keywords that map to enhancement types
ENHANCEMENT_KEYWORDS: dict[str, EnhancementType] = {
    "acceptance criteria": EnhancementType.ACCEPTANCE_CRITERIA,
    "acceptance": EnhancementType.ACCEPTANCE_CRITERIA,
    "criteria": EnhancementType.ACCEPTANCE_CRITERIA,
    "ac": EnhancementType.ACCEPTANCE_CRITERIA,
    "edge case": EnhancementType.EDGE_CASES,
    "edge cases": EnhancementType.EDGE_CASES,
    "edge": EnhancementType.EDGE_CASES,
    "error": EnhancementType.EDGE_CASES,
    "failure": EnhancementType.EDGE_CASES,
    "bdd": EnhancementType.BDD_SCENARIOS,
    "given when then": EnhancementType.BDD_SCENARIOS,
    "scenario": EnhancementType.BDD_SCENARIOS,
    "behavior": EnhancementType.BDD_SCENARIOS,
    "technical": EnhancementType.TECHNICAL_NOTES,
    "tech notes": EnhancementType.TECHNICAL_NOTES,
    "implementation": EnhancementType.TECHNICAL_NOTES,
    "architecture": EnhancementType.TECHNICAL_NOTES,
    "dependencies": EnhancementType.DEPENDENCIES,
    "depends on": EnhancementType.DEPENDENCIES,
    "dependency": EnhancementType.DEPENDENCIES,
    "complexity": EnhancementType.COMPLEXITY,
    "effort": EnhancementType.COMPLEXITY,
    "estimate": EnhancementType.COMPLEXITY,
    "points": EnhancementType.COMPLEXITY,
}


def detect_story_reference(text: str, stories: list[UserStory]) -> UserStory | None:
    """
    Detect which story the user is referring to in their message.

    Supports:
    - Story IDs: "STORY-001", "story 1", "#1"
    - Story numbers: "first story", "second story", "story 2"
    - Story titles: partial match on title
    """
    text_lower = text.lower()

    # Match by ID pattern (STORY-XXX)
    id_match = re.search(r"(story[-\s]?\d+|#\d+)", text_lower)
    if id_match:
        # Extract the number
        num_match = re.search(r"\d+", id_match.group())
        if num_match:
            idx = int(num_match.group()) - 1  # Convert to 0-based index
            if 0 <= idx < len(stories):
                return stories[idx]

    # Match by ordinal: "first", "second", "third", etc.
    ordinals = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
    for i, ordinal in enumerate(ordinals):
        if ordinal in text_lower:
            if i < len(stories):
                return stories[i]

    # Match by title (partial)
    for story in stories:
        if story.title.lower() in text_lower:
            return story

    return None


def detect_enhancement_type(text: str) -> EnhancementType:
    """Detect the enhancement type from user's message."""
    text_lower = text.lower()

    for keyword, enhancement_type in ENHANCEMENT_KEYWORDS.items():
        if keyword in text_lower:
            return enhancement_type

    # Default to full enhancement
    return EnhancementType.FULL


class StoryEnhanceNode:
    """
    Enhance a specific story with targeted improvements.

    This node handles requests like:
    - "Add more edge cases to story 2"
    - "Enhance the first story with BDD scenarios"
    - "Add technical notes to STORY-003"

    Usage:
        node = StoryEnhanceNode(config=BacklogAgentConfig())
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
        Enhance a specific story based on user request.

        Args:
            state: Current agent state with stories and refinement_feedback

        Returns:
            State update with enhanced story
        """
        logger.info("StoryEnhanceNode: Processing enhancement request")

        feedback = state.get("refinement_feedback", "")
        current_result = state.get("current_result")
        stories = state.get("stories", [])

        if not feedback:
            return {"error": "No enhancement request provided"}

        if not stories:
            return {"error": "No stories to enhance. Please decompose an epic first."}

        # Convert stories from dicts if needed
        if stories and isinstance(stories[0], dict):
            stories = [UserStory.model_validate(s) for s in stories]

        # Detect which story to enhance
        target_story = detect_story_reference(feedback, stories)
        if not target_story:
            # If no specific story mentioned, ask for clarification
            return {
                "help_response": self._generate_story_selection_prompt(stories, feedback),
                "error": None,
            }

        # Detect enhancement type
        enhancement_type = detect_enhancement_type(feedback)

        logger.info(f"StoryEnhanceNode: Enhancing {target_story.id} with {enhancement_type.value}")

        try:
            if self.config.USE_MOCKS:
                enhanced_story = await self._mock_enhance(target_story, enhancement_type, feedback)
            else:
                enhanced_story = await self._llm_enhance(target_story, enhancement_type, feedback)

            # Replace the story in the list
            updated_stories = []
            for story in stories:
                if story.id == target_story.id:
                    updated_stories.append(enhanced_story)
                else:
                    updated_stories.append(story)

            # Update current_result if it exists
            updated_result = None
            if current_result:
                if isinstance(current_result, dict):
                    current_result = DecompositionResult.model_validate(current_result)
                updated_result = current_result.model_copy(update={"stories": updated_stories})

            return {
                "stories": updated_stories,
                "current_result": updated_result,
                "refinement_feedback": None,
                "error": None,
            }

        except Exception as e:
            logger.error(f"StoryEnhanceNode: Error - {e}")
            return {"error": f"Enhancement failed: {str(e)}"}

    def _generate_story_selection_prompt(self, stories: list[UserStory], feedback: str) -> str:
        """Generate a prompt asking user to specify which story."""
        story_list = "\n".join(f"- **{i + 1}. {s.id}**: {s.title}" for i, s in enumerate(stories))

        return f"""I'd love to help enhance a story! Which one would you like me to improve?

## Available Stories:
{story_list}

Please specify the story by number (e.g., "enhance story 1" or "add edge cases to {stories[0].id}")

**Your request**: {feedback}
"""

    async def _mock_enhance(
        self,
        story: UserStory,
        enhancement_type: EnhancementType,
        feedback: str,
    ) -> UserStory:
        """Apply mock enhancement for testing."""
        logger.info(f"StoryEnhanceNode: Mock enhancing {story.id}")

        # Create a copy of the story
        enhanced = story.model_copy(deep=True)

        if enhancement_type == EnhancementType.ACCEPTANCE_CRITERIA:
            enhanced.acceptance_criteria.extend(
                [
                    AcceptanceCriteria(description="System validates input before processing"),
                    AcceptanceCriteria(description="User receives confirmation on success"),
                    AcceptanceCriteria(description="Error message is shown on failure"),
                ]
            )

        elif enhancement_type == EnhancementType.EDGE_CASES:
            enhanced.edge_cases.extend(
                [
                    "Handle empty or null input gracefully",
                    "Handle concurrent requests without race conditions",
                    "Handle network timeout and retry appropriately",
                    "Handle maximum size limits exceeded",
                ]
            )

        elif enhancement_type == EnhancementType.BDD_SCENARIOS:
            enhanced.acceptance_criteria.extend(
                [
                    AcceptanceCriteria(
                        description="GIVEN a valid user, WHEN they submit the form, THEN the request is processed"
                    ),
                    AcceptanceCriteria(
                        description="GIVEN invalid data, WHEN validation runs, THEN appropriate errors are shown"
                    ),
                ]
            )

        elif enhancement_type == EnhancementType.TECHNICAL_NOTES:
            enhanced.technical_notes.extend(
                [
                    "Consider using async processing for improved performance",
                    "Implement proper error handling with structured logging",
                    "Add database transaction support for data integrity",
                ]
            )

        elif enhancement_type == EnhancementType.DEPENDENCIES:
            if not enhanced.dependencies:
                enhanced.dependencies = []
            enhanced.dependencies.append("Authentication service must be available")

        elif enhancement_type == EnhancementType.COMPLEXITY:
            enhanced.estimated_complexity = "M"
            enhanced.business_value_score = 75
            enhanced.effort_score = 40

        else:  # FULL enhancement
            enhanced.acceptance_criteria.append(
                AcceptanceCriteria(description="Full validation and error handling implemented")
            )
            enhanced.edge_cases.append("Handle all error scenarios gracefully")
            enhanced.technical_notes.append("Comprehensive testing required")

        return enhanced

    async def _llm_enhance(
        self,
        story: UserStory,
        enhancement_type: EnhancementType,
        feedback: str,
    ) -> UserStory:
        """Use LLM to enhance the story."""
        if not self.llm_service:
            self.llm_service = get_llm_service()

        # Build prompts
        story_json = story.model_dump_json(indent=2)

        system_prompt = f"""You are a story enhancement specialist.
You will be given a user story and asked to enhance it with {enhancement_type.value}.

Current story:
{story_json}

Respond with the COMPLETE enhanced story in the same JSON format.
Add high-quality, specific, and actionable {enhancement_type.value}.
Do not remove any existing content - only add new enhancements.
"""

        user_prompt = f"Enhance this story based on the request: {feedback}"

        # Use structured output validator
        result_data, _ = await self.validator.with_retry(
            llm=self.llm_service,
            prompt=user_prompt,
            schema=UserStory,
            max_retries=self.config.MAX_RETRIES,
            system_prompt=system_prompt,
        )

        return result_data


# Convenience function for standalone testing
async def story_enhance_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for StoryEnhanceNode."""
    node = StoryEnhanceNode(config=config)
    return await node(state)
