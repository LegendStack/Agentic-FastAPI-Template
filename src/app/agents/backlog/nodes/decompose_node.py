"""
Decompose Node
==============
Core story decomposition logic using LLM with structured output.
Generates user stories from an epic description.
"""

import logging
from typing import Any

from ....core.config import settings
from ...azure_openai import LLMService, get_llm_service
from ...structured_output import StructuredOutputValidator
from ...vector_stores import VectorStoreFactory
from ..config import BacklogAgentConfig
from ..intents import UserIntent
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
                business_value_score=50,
                effort_score=50,
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
                business_value_score=100,
                effort_score=20,
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
                business_value_score=80,
                effort_score=40,
                tags=["testing", "quality"],
            ),
        ]

        return DecompositionResult(
            epic=epic,
            stories=stories,
            conversation_title=f"{epic.title[:30]} Breakdown",
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
        # Double safety check: If use_mocks is not explicitly set to False in initialization,
        # and we are in a factory or API context, ensure we respect the global override if provided.
        # But here, we just want to be sure it's not unintentionally True.
        self.llm_service = llm_service or get_llm_service()
        self.validator = StructuredOutputValidator()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Decompose the epic in state into user stories.

        Args:
            state: Current agent state with parsed_epic

        Returns:
            State update with stories and current_result
        """
        logger.info(
            f"DecomposeNode: Starting decomposition (USE_MOCKS={self.config.USE_MOCKS}, global_settings={settings.BACKLOG_USE_MOCKS})"
        )

        parsed_epic = state.get("parsed_epic")
        if not parsed_epic:
            return {"error": "No parsed epic in state"}

        # Convert from dict if needed
        if isinstance(parsed_epic, dict):
            parsed_epic = Epic.model_validate(parsed_epic)

        try:
            # 0. Initial parameters
            detected_intent = state.get("detected_intent", UserIntent.DECOMPOSE.value)
            target_level = "story"
            target_issue_type = self.config.JIRA_ISSUE_TYPE

            if self.config.USE_MOCKS:
                result = await self._mock_decompose(parsed_epic)
                usage = {}
            else:
                # 1. Semantic Deduplication Check
                duplicate_info = await self._check_duplicate_epic(parsed_epic)
                if duplicate_info and self.config.PREVENT_DUPLICATE_DECOMPOSITION:
                    logger.info(
                        f"DecomposeNode: Semantic duplicate detected. Thread ID: {duplicate_info.get('thread_id')}"
                    )

                # 2. Retrieve similar stories for context (Phase 13)
                reference_stories = await self._retrieve_reference_stories(parsed_epic)

                # 3. Get enriched context from entity extraction (Phase 5)
                enriched_context = state.get("enriched_context", "")

                # 4. LLM Decomposition with full context
                if detected_intent == UserIntent.DECOMPOSE_TO_EPICS.value:
                    target_level = "epic"
                    target_issue_type = self.config.JIRA_EPIC_ISSUE_TYPE
                elif detected_intent == UserIntent.DECOMPOSE_TO_STORIES.value:
                    target_level = "story"
                    target_issue_type = "Story"
                elif detected_intent == UserIntent.DECOMPOSE_TO_TASKS.value:
                    target_level = "task"
                    target_issue_type = "Task"
                elif detected_intent == UserIntent.DECOMPOSE_TO_SUBTASKS.value:
                    target_level = "subtask"
                    target_issue_type = "Sub-task"

                story_template = state.get("story_template", self.config.STORY_TEMPLATE)
                result, usage = await self._llm_decompose(
                    parsed_epic,
                    target_level=target_level,
                    reference_stories=reference_stories,
                    story_template=story_template,
                    enriched_context=enriched_context,
                )

            # Step 5: Post-processing (only if not using mocks and result is valid)
            if not self.config.USE_MOCKS and result:
                if not result.stories:
                    logger.error("DecomposeNode: LLM returned empty stories list")
                    return {
                        "error": "Decomposition returned no user stories. Please try a more detailed epic description."
                    }

                logger.info(f"DecomposeNode: Generated {len(result.stories)} stories")

                # Detect duplicates for generated stories
                await self._detect_duplicates(result.stories)

                # Archive this epic for future deduplication
                await self._archive_epic(parsed_epic, state.get("thread_id"))
            return {
                "stories": result.stories if result else [],
                "current_result": result,
                "usage_metadata": usage,
                "target_issue_type": target_issue_type,
                "is_first_message": False,
                "error": None,
            }

        except Exception as e:
            return {"error": f"Decomposition failed: {str(e)}"}

    async def _check_duplicate_epic(self, epic: Epic) -> dict[str, Any] | None:
        """Check if this epic has already been decomposed."""
        try:
            store = VectorStoreFactory.get_store(None)
            if not self.llm_service:
                self.llm_service = get_llm_service()

            query_vector = await self.llm_service.get_embeddings(epic.description)

            # Search for epics in the archive
            results = await store.similarity_search(query_vector, k=1, filters={"source_id": "epic_archive"})
            if results:
                match = results[0]
                score = match.get("score", 0)
                # High threshold for semantic clone
                if score > 0.92:
                    logger.info(f"DecomposeNode: Found duplicate epic (score: {score:.4f})")
                    meta = match.get("metadata", {})
                    return {"thread_id": meta.get("thread_id"), "title": meta.get("title"), "score": score}

            return None
        except Exception as e:
            logger.warning(f"DecomposeNode: Duplicate check failed - {e}")
            return None

    async def _archive_epic(self, epic: Epic, thread_id: str) -> None:
        """Archive epic description to allow future deduplication."""
        if not thread_id:
            return

        try:
            store = VectorStoreFactory.get_store(None)
            if not self.llm_service:
                self.llm_service = get_llm_service()

            embedding = await self.llm_service.get_embeddings(epic.description)

            doc = {
                "content": epic.description,
                "embedding": embedding,
                "metadata": {
                    "type": "epic",
                    "title": epic.title,
                    "thread_id": thread_id,
                    "project_key": epic.project_key,
                },
                "source_id": "epic_archive",
                "tenant_id": "default",
            }

            await store.add_documents([doc])
            logger.info(f"DecomposeNode: Archived epic '{epic.title}' for deduplication")

        except Exception as e:
            logger.warning(f"DecomposeNode: Failed to archive epic - {e}")

    async def _mock_decompose(self, epic: Epic) -> DecompositionResult:
        """Generate mock decomposition for testing."""
        logger.info("DecomposeNode: Using mock decomposition")
        return MockDecomposeResult.generate(epic, self.config)

    async def _llm_decompose(
        self,
        epic: Epic,
        target_level: str = "story",
        reference_stories: list[UserStory] | None = None,
        story_template: str = "standard",
        enriched_context: str = "",
    ) -> tuple[DecompositionResult, dict[str, Any]]:
        """Use LLM to decompose the epic."""
        if not self.llm_service:
            self.llm_service = get_llm_service()

        # Build context from reference stories
        context = epic.context or ""

        # Add enriched context from Jira entity extraction (Phase 5)
        if enriched_context:
            context += "\n\n" + enriched_context
            logger.info("DecomposeNode: Enriched context added (%d chars)", len(enriched_context))

        if reference_stories:
            context += "\n\n### Reference Examples from Past Stories:\n"
            for s in reference_stories:
                context += f"- **{s.title}**: {s.description}\n"
                if s.acceptance_criteria:
                    context += "  Acceptance Criteria:\n"
                    for ac in s.acceptance_criteria:
                        desc = ac.description if hasattr(ac, "description") else str(ac)
                        context += f"  * {desc}\n"

        # Build prompts
        system_prompt = get_decompose_system_prompt(
            target_level=target_level,
            story_template=story_template,
            ac_style=self.config.AC_STYLE,
            project_key=epic.project_key,
        )

        user_prompt = get_decompose_user_prompt(
            epic_description=epic.description,
            target_level=target_level,
            context=context.strip(),
            min_stories=self.config.MIN_STORIES_PER_EPIC,
            max_stories=self.config.MAX_STORIES_PER_EPIC,
            min_ac=self.config.MIN_AC_PER_STORY,
            enable_edge_cases=self.config.ENABLE_EDGE_CASES,
            enable_tech_tasks=self.config.ENABLE_TECH_TASKS,
            enable_dependencies=self.config.ENABLE_DEPENDENCIES,
            enable_complexity=self.config.ENABLE_COMPLEXITY_ESTIMATION,
        )

        logger.info("DecomposeNode: Final context length: %d chars", len(context))
        logger.info("DecomposeNode: SYSTEM PROMPT SNIPPET: %s", system_prompt[:200])
        logger.info("DecomposeNode: USER PROMPT SNIPPET: %s", user_prompt[:200])

        # Use structured output validator with retry
        result_data, usage_metadata = await self.validator.with_retry(
            llm=self.llm_service,
            prompt=user_prompt,
            schema=DecompositionResult,
            max_retries=self.config.MAX_RETRIES,
            system_prompt=system_prompt,
        )

        # Ensure epic is set correctly
        result_data.epic = epic

        logger.debug(f"DecomposeNode: Raw result stories ID: {[s.id for s in result_data.stories]}")

        return result_data, usage_metadata

    async def _retrieve_reference_stories(self, epic: Epic) -> list[UserStory]:
        """Retrieve similar stories from Azure AI Search."""
        logger.info(f"DecomposeNode: Retrieving reference stories for: '{epic.description[:50]}...'")
        try:
            # We need a DB session for the factory, but Azure Search store doesn't actually use it
            # We'll use a dummy call to async_get_db if needed, but get_store(None) might work for Azure Search
            store = VectorStoreFactory.get_store(None)

            # Embed the epic description
            if not self.llm_service:
                self.llm_service = get_llm_service()

            query_vector = await self.llm_service.get_embeddings(epic.description)

            # Search for top candidates (fetching more for reranking)
            # Use hybrid search if available, otherwise vector search
            if hasattr(store, "similarity_search_hybrid"):
                results = await store.similarity_search_hybrid(query=epic.description, query_vector=query_vector, k=10)
            else:
                results = await store.similarity_search(query_vector, k=10)

            # Rerank results
            from ...reranking import KeywordBonusReranker, RerankingService

            reranker = RerankingService(KeywordBonusReranker(bonus_weight=0.5))
            results = await reranker.rerank(epic.description, results, top_k=3)

            stories = []
            for r in results:
                try:
                    score = r.get("score", 0)
                    content = r.get("content", "")
                    title = r.get("metadata", {}).get("title", "Past Story")

                    logger.info(f"DecomposeNode: Found potential reference - '{title}' (Score: {score:.4f})")

                    # Threshold for reference examples - only use if reasonably similar
                    # 0.3 is a more conservative threshold for Azure Search hybrid scores
                    if score < 0.3:
                        logger.info(
                            f"DecomposeNode: Skipping low-score reference story '{title}' (score: {score:.4f} < 0.3)"
                        )
                        continue

                    stories.append(
                        UserStory(id=r.get("id", "REF"), title=title, description=content[:500], acceptance_criteria=[])
                    )
                except Exception as e:
                    logger.warning(f"DecomposeNode: Error parsing reference story - {e}")
                    continue

            if stories:
                ref_titles = [s.title for s in stories]
                logger.info(f"DecomposeNode: Using {len(stories)} reference stories: {ref_titles}")
            else:
                logger.info("DecomposeNode: No reference stories found")
            return stories
        except Exception as e:
            logger.warning(f"DecomposeNode: Failed to retrieve reference stories - {e}")
            return []

    async def _detect_duplicates(self, stories: list[UserStory]) -> None:
        """
        Check each generated story for potential duplicates in Azure AI Search.
        Updates the story objects in-place with is_duplicate and duplicate_reason.
        """
        logger.info(f"DecomposeNode: Performing duplicate detection for {len(stories)} stories")
        try:
            store = VectorStoreFactory.get_store(None)
            if not self.llm_service:
                self.llm_service = get_llm_service()

            for story in stories:
                # 1. Search for similar stories using hybrid search (Vector + Title)
                query_vector = await self.llm_service.get_embeddings(story.description)

                # We use the title as search_text for better keyword matching
                # and vector for semantic matching.
                results = await store.similarity_search(query_vector, k=1, search_text=story.title)

                if results:
                    top_match = results[0]
                    score = top_match.get("score", 0)

                    # Threshold for considering it a "Potential Duplicate"
                    # 0.1 is a more reliable threshold for Azure Search hybrid scores
                    if score > 0.1:
                        story.is_duplicate = True
                        match_title = top_match.get("metadata", {}).get("title", "Existing Story")
                        match_id = top_match.get("metadata", {}).get("story_id", "Unknown")
                        story.duplicate_reason = (
                            f"Potential overlap with existing story: [{match_id}] {match_title}. "
                            f"(Match Score: {score:.4f})"
                        )
                        logger.info(f"DecomposeNode: story {story.id} flagged as duplicate of {match_id}")

        except Exception as e:
            logger.warning(f"DecomposeNode: Duplicate detection failed - {e}")


# Convenience function for standalone testing
async def decompose_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for DecomposeNode."""
    node = DecomposeNode(config=config)
    return await node(state)
