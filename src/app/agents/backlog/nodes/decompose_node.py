"""
Decompose Node
==============
Core story decomposition logic using LLM with structured output.
Generates user stories from an epic description.
"""

import logging
from typing import Any

from ...azure_openai import LLMService
from ...structured_output import StructuredOutputValidator
from ..config import BacklogAgentConfig
from ..prompts import get_decompose_system_prompt, get_decompose_user_prompt, get_refine_system_prompt
from ..schemas import AcceptanceCriteria, DecompositionResult, Epic, UserStory
from ..state import BacklogAgentState
from ....core.db.database import async_get_db
from ...vector_stores import VectorStoreFactory

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
                "Add BDD scenarios to all stories",
                "Split STORY-002 into frontend/backend tasks",
                "Save to JIRA",
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
                # 1. Retrieve similar stories for context (Phase 13)
                reference_stories = await self._retrieve_reference_stories(parsed_epic)
                
                # 2. LLM Decomposition with context
                result = await self._llm_decompose(parsed_epic, reference_stories=reference_stories)

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

    async def _llm_decompose(self, epic: Epic, reference_stories: list[UserStory] | None = None) -> DecompositionResult:
        """Use LLM to decompose the epic."""
        if not self.llm_service:
            self.llm_service = LLMService()

        # Build context from reference stories
        context = epic.context or ""
        if reference_stories:
            context += "\n\n### Reference Examples from Past Stories:\n"
            for s in reference_stories:
                context += f"- **{s.title}**: {s.description}\n"
                if s.acceptance_criteria:
                    context += "  Acceptance Criteria:\n"
                    for ac in s.acceptance_criteria:
                        desc = ac.description if hasattr(ac, 'description') else str(ac)
                        context += f"  * {desc}\n"

        # Build prompts
        system_prompt = get_decompose_system_prompt(
            story_template=self.config.STORY_TEMPLATE,
            ac_style=self.config.AC_STYLE,
            project_key=epic.project_key,
        )

        user_prompt = get_decompose_user_prompt(
            epic_description=epic.description,
            context=context.strip(),
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

    async def _retrieve_reference_stories(self, epic: Epic) -> list[UserStory]:
        """Retrieve similar stories from Azure AI Search."""
        logger.info("DecomposeNode: Retrieving reference stories")
        try:
            # We need a DB session for the factory, but Azure Search store doesn't actually use it
            # We'll use a dummy call to async_get_db if needed, but get_store(None) might work for Azure Search
            store = VectorStoreFactory.get_store(None)
            
            # Embed the epic description
            if not self.llm_service:
                self.llm_service = LLMService()
            
            query_vector = await self.llm_service.get_embeddings(epic.description)
            
            # Search for top 3 similar stories
            results = await store.similarity_search(query_vector, k=3)
            
            stories = []
            for r in results:
                try:
                    # Content is usually a stringified JSON or plain text
                    # If it's a story, we can try to parse it
                    content = r.get("content", "")
                    # For now, let's just create a simple reference story
                    stories.append(UserStory(
                        id=r.get("id", "REF"),
                        title=r.get("metadata", {}).get("title", "Past Story"),
                        description=content[:500],
                        acceptance_criteria=[] # Not strictly needed for context
                    ))
                except Exception:
                    continue
            
            return stories
        except Exception as e:
            logger.warning(f"DecomposeNode: Failed to retrieve reference stories - {e}")
            return []


# Convenience function for standalone testing
async def decompose_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for DecomposeNode."""
    node = DecomposeNode(config=config)
    return await node(state)
