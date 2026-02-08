"""
Test Generation Node
====================
Generates Gherkin test scenarios for user stories.
"""

import logging
from typing import Any

from ...azure_openai import get_llm_service
from ..config import BacklogAgentConfig
from ..schemas import DecompositionResult, UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class TestGenNode:
    """
    Generates Gherkin test scenarios for user stories.

    Acts as a QA Automation engineer, converting Acceptance Criteria
    into structured Given/When/Then scenarios.
    """

    def __init__(self, config: BacklogAgentConfig | None = None):
        self.config = config or BacklogAgentConfig()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Generate tests for all stories in the current result.
        """
        logger.info("TestGenNode: Generating test scenarios")

        current_result = state.get("current_result")
        if not current_result:
            return {"error": "No decomposition result to generate tests for"}

        # Convert from dict if needed
        if isinstance(current_result, dict):
            current_result = DecompositionResult.model_validate(current_result)

        # If result has no stories, skip
        if not current_result.stories:
            logger.info("TestGenNode: No stories to test.")
            return {"stories": []}

        # Select stories to process (skip those that already have tests if we want incrementally?
        # For now, regenerate to ensure freshness)
        target_stories = current_result.stories

        # We can process in parallel batches if needed, but for now sequential for simplicity
        updated_stories = []

        # Use LLM Service
        llm = get_llm_service()

        for story in target_stories:
            try:
                scenarios = await self._generate_scenarios(llm, story)
                story.test_scenarios = scenarios
                updated_stories.append(story)
            except Exception as e:
                logger.error(f"TestGenNode: Failed to generate tests for {story.id} - {e}")
                updated_stories.append(story)  # Keep original without tests on failure

        logger.info(f"TestGenNode: Generated tests for {len(updated_stories)} stories")

        return {
            "stories": updated_stories,
            "current_result": current_result,  # Propagate the updated object
        }

    async def _generate_scenarios(self, llm: Any, story: UserStory) -> list[str]:
        """Generate Gherkin scenarios for a single story."""

        ac_text = "\n".join([f"- {ac.description}" for ac in story.acceptance_criteria])

        prompt = f"""You are a QA Automation Engineer. Generate 3 Gherkin (Given/When/Then) test scenarios for this User Story.
        
        Story: {story.title}
        Description: {story.description}
        
        Acceptance Criteria:
        {ac_text}
        
        Rules:
        1. Output ONLY the Gherkin scenarios.
        2. Wrap EACH scenario individually in triple backticks with the "gherkin" language tag: ```gherkin ... ```
        3. Separate these code blocks with a line containing exactly "---"
        4. Use standard Given/When/Then syntax.
        5. Cover positive and negative cases if possible.
        """

        response = await llm.chat([{"role": "user", "content": prompt}])
        content = response.content.strip()

        # Split by separator and clean up
        import re

        raw_scenarios = content.split("---")
        clean_scenarios = []
        for s in raw_scenarios:
            s_clean = s.strip()
            if not s_clean:
                continue

            # Remove any existing code block markers and "gherkin" tags
            # We strip all triple backticks and common prefixes to re-standardize
            s_clean = re.sub(r"```gherkin\s*", "", s_clean, flags=re.IGNORECASE)
            s_clean = re.sub(r"```\s*", "", s_clean)

            # Remove "Scenario X:" or "Scenario:" if the LLM added them outside/inside
            s_clean = re.sub(r"^Scenario\s+\d+:?\s*", "", s_clean, flags=re.IGNORECASE | re.MULTILINE)
            s_clean = re.sub(r"^Scenario:?\s*", "", s_clean, flags=re.IGNORECASE | re.MULTILINE)

            # Final trim as raw text (no backticks)
            s_clean = s_clean.strip()
            if not s_clean:
                continue

            clean_scenarios.append(s_clean)

        return clean_scenarios[:5]  # Limit to 5 max
