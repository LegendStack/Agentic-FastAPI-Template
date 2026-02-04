"""
Decompose Node
==============
Core story decomposition logic using LLM with structured output.
Generates user stories from an epic description.
"""

import json
import logging
from typing import Any

from ...azure_openai import LLMService
from ...structured_output import StructuredOutputValidator
from ..config import BacklogAgentConfig
from ..prompts import get_decompose_system_prompt, get_decompose_user_prompt
from ..schemas import AcceptanceCriteria, DecompositionResult, Epic, UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class MockDecomposeResult:
    """Mock decomposition for testing without LLM."""

    @staticmethod
    def generate(epic: Epic, config: BacklogAgentConfig) -> DecompositionResult:
        """Generate a mock decomposition result."""
        stories = [
            UserStory(
                id="STORY-001",
                title=f"Initial Setup for {epic.title[:30]}",
                description=f"As a developer, I want to set up the foundation for {epic.title}, so that we can build upon it.",
                acceptance_criteria=[
                    AcceptanceCriteria(description="Project structure is created"),
                    AcceptanceCriteria(description="Basic configuration is in place"),
                    AcceptanceCriteria(description="Development environment works"),
                ],
                edge_cases=["Handle missing configuration gracefully"] if config.ENABLE_EDGE_CASES else [],
                technical_notes=["Consider using existing patterns"] if config.ENABLE_TECH_TASKS else [],
                estimated_complexity="M" if config.ENABLE_COMPLEXITY_ESTIMATION else None,
                tags=["setup", "infrastructure"],
            ),
            UserStory(
                id="STORY-002",
                title=f"Core Implementation for {epic.title[:30]}",
                description=f"As a user, I want the main functionality of {epic.title}, so that I can achieve my goal.",
                acceptance_criteria=[
                    AcceptanceCriteria(description="Main feature is functional"),
                    AcceptanceCriteria(description="User can complete the workflow"),
                    AcceptanceCriteria(description="Success feedback is shown"),
                ],
                edge_cases=["Handle invalid input", "Handle network errors"] if config.ENABLE_EDGE_CASES else [],
                dependencies=["STORY-001"] if config.ENABLE_DEPENDENCIES else [],
                estimated_complexity="L" if config.ENABLE_COMPLEXITY_ESTIMATION else None,
                tags=["core", "feature"],
            ),
            UserStory(
                id="STORY-003",
                title=f"Testing and Validation for {epic.title[:30]}",
                description=f"As a QA engineer, I want comprehensive tests for {epic.title}, so that we ensure quality.",
                acceptance_criteria=[
                    AcceptanceCriteria(description="Unit tests cover main logic"),
                    AcceptanceCriteria(description="Integration tests pass"),
                    AcceptanceCriteria(description="Edge cases are tested"),
                ],
                dependencies=["STORY-002"] if config.ENABLE_DEPENDENCIES else [],
                estimated_complexity="M" if config.ENABLE_COMPLEXITY_ESTIMATION else None,
                tags=["testing", "quality"],
            ),
        ]

        return DecompositionResult(
            epic=epic,
            stories=stories,
            summary=f"Decomposed '{epic.title}' into {len(stories)} user stories covering setup, core implementation, and testing.",
            recommendations=[
                "Consider adding documentation story",
                "Plan for incremental delivery",
            ],
            total_estimated_effort="M-L (approximately 2-3 sprints)",
        )


class DecomposeNode:
    """
    Decompose an epic into user stories using LLM.

    Uses structured output validation to ensure reliable JSON responses.
    Supports mock mode for testing without LLM calls.

    Usage:
        node = DecomposeNode(config=BacklogAgentConfig())
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
        Decompose the epic in state into user stories.

        Args:
            state: Current agent state with parsed_epic

        Returns:
            State update with stories and current_result
        """
        logger.info("DecomposeNode: Starting decomposition")

        parsed_epic = state.get("parsed_epic")
        if not parsed_epic:
            return {"error": "No parsed epic in state"}

        # Convert from dict if needed
        if isinstance(parsed_epic, dict):
            parsed_epic = Epic.model_validate(parsed_epic)

        try:
            if self.config.USE_MOCKS:
                result = await self._mock_decompose(parsed_epic)
            else:
                result = await self._llm_decompose(parsed_epic)

            logger.info(f"DecomposeNode: Generated {len(result.stories)} stories")

            return {
                "stories": result.stories,
                "current_result": result,
                "is_first_message": False,  # After decomposition, next message is refinement
                "error": None,
            }

        except Exception as e:
            logger.error(f"DecomposeNode: Error - {e}")
            return {"error": f"Decomposition failed: {str(e)}"}

    async def _mock_decompose(self, epic: Epic) -> DecompositionResult:
        """Generate mock decomposition for testing."""
        logger.info("DecomposeNode: Using mock decomposition")
        return MockDecomposeResult.generate(epic, self.config)

    async def _llm_decompose(self, epic: Epic) -> DecompositionResult:
        """Use LLM to decompose the epic."""
        if not self.llm_service:
            self.llm_service = LLMService()

        # Build prompts
        system_prompt = get_decompose_system_prompt(
            story_template=self.config.STORY_TEMPLATE,
            ac_style=self.config.AC_STYLE,
        )

        user_prompt = get_decompose_user_prompt(
            epic_description=epic.description,
            context=epic.context,
            min_stories=self.config.MIN_STORIES_PER_EPIC,
            max_stories=self.config.MAX_STORIES_PER_EPIC,
            min_ac=self.config.MIN_AC_PER_STORY,
            enable_edge_cases=self.config.ENABLE_EDGE_CASES,
            enable_tech_tasks=self.config.ENABLE_TECH_TASKS,
            enable_dependencies=self.config.ENABLE_DEPENDENCIES,
            enable_complexity=self.config.ENABLE_COMPLEXITY_ESTIMATION,
        )

        # Use structured output validator with retry
        result = await self.validator.with_retry(
            llm=self.llm_service,
            prompt=user_prompt,
            schema=DecompositionResult,
            max_retries=self.config.MAX_RETRIES,
            system_prompt=system_prompt,
        )

        # Ensure epic is set correctly
        result.epic = epic

        return result


# Convenience function for standalone testing
async def decompose_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for DecomposeNode."""
    node = DecomposeNode(config=config)
    return await node(state)
