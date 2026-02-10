"""
Input Node
==========
Parses and validates the incoming epic description.
Determines if this is a new decomposition or a refinement request.
"""

import logging
import re
from typing import Any

from ..schemas import Epic, UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class InputNode:
    """
    Parse and validate user input for the backlog agent.

    Responsibilities:
    - Extract epic title and description from user input
    - Detect if this is a new decomposition or refinement
    - Validate input isn't empty or too short
    - Parse any additional context provided

    Usage:
        node = InputNode()
        updated_state = await node(state)
    """

    MIN_INPUT_LENGTH = 10
    MAX_INPUT_LENGTH = 10000

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Process user input and update state.

        Args:
            state: Current agent state

        Returns:
            State update dict with parsed epic and flow flags
        """
        logger.info("InputNode: Processing user input")

        messages = state.get("messages", [])
        if not messages:
            logger.error("InputNode: No messages in state")
            return {"error": "No input provided"}

        # Get the latest user message
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if not user_message:
            return {"error": "No user message found"}

        logger.info(f"InputNode: User message: '{user_message[:100]}...'")

        # Validate input length
        min_length = self.MIN_INPUT_LENGTH
        parent_epic_id = state.get("parent_epic_id")

        # Relax validation if we have sticky context (sidebar selection)
        if parent_epic_id:
            min_length = 1  # Anything goes if we have context
            logger.info(f"InputNode: Relaxing min_length to 1 due to parent_epic_id={parent_epic_id}")

        if len(user_message) < min_length:
            return {
                "error": f"Input too short. Please provide at least {min_length} characters describing the epic."
            }

        if len(user_message) > self.MAX_INPUT_LENGTH:
            user_message = user_message[: self.MAX_INPUT_LENGTH]
            logger.warning(f"InputNode: Input truncated to {self.MAX_INPUT_LENGTH} characters")

        # Determine if this is a new decomposition or refinement
        is_first_message = state.get("is_first_message", True)
        existing_stories = state.get("stories", [])

        # HYDRATION DETECTION: If stories are already present in the state (e.g. from /refine endpoint)
        if existing_stories and is_first_message:
            logger.info("InputNode: Detected pre-populated stories (Hydration)")

            # NORMALIZE: Ensure stories are dicts or UserStory objects for DecompositionResult
            normalized_stories = []
            for s in existing_stories:
                if hasattr(s, "model_dump"):
                    normalized_stories.append(s.model_dump())
                else:
                    normalized_stories.append(s)

            # Create a shell result for the graph to proceed
            from ..schemas import DecompositionResult, Epic

            project_key = state.get("project_key")
            shell_epic = Epic(
                title="Imported stories", description="Refining pre-populated stories", project_key=project_key
            )
            shell_result = DecompositionResult(
                epic=shell_epic,
                stories=normalized_stories,  # Use normalized ones
                summary="Imported stories for refinement",
            )

            return {
                "refinement_feedback": user_message,
                "current_result": shell_result,
                "stories": normalized_stories,  # Also update the state stories to normalized versions
                "is_first_message": False,
                "error": None,
            }

        is_save_requested = self._is_save_intent(user_message)

        if is_save_requested and existing_stories:
            logger.info("InputNode: Detected save intent for existing stories")
            return {
                "refinement_feedback": None,
                "is_save_requested": True,
                "is_first_message": False,
                "manual_edits_detected": False,  # Edits not relevant for pure save but good to initialize
                "edit_context": None,
                "stories": existing_stories,  # Preserve stories
                "error": None,
            }

        if existing_stories and not is_first_message:
            # Detect if this is a "Pivot": starting a new epic in the same thread
            if self._is_new_epic_intent(user_message, existing_stories):
                logger.info("InputNode: Detected pivot to new epic. Resetting state.")
                parsed_epic = self._parse_epic(user_message, project_key=project_key)
                return {
                    "epic_input": user_message,
                    "parsed_epic": parsed_epic,
                    "stories": [],  # Reset stories for new epic
                    "current_result": None,
                    "is_first_message": True,  # Treat as first message to trigger DecomposeNode
                    "refinement_feedback": None,
                    "is_save_requested": False,
                    "manual_edits_detected": False,
                    "edit_context": None,
                    "error": None,
                }

            # This is a refinement request
            logger.info("InputNode: Detected refinement request")

            # Phase 27: Detect manual edits
            manual_edits_detected, edit_context = self._detect_manual_edits(
                incoming_stories=state.get("stories", []), existing_stories=existing_stories
            )

            if manual_edits_detected:
                logger.info(f"InputNode: Manual edits detected: {edit_context}")

            return {
                "refinement_feedback": user_message,
                "is_save_requested": False,
                "is_first_message": False,
                "manual_edits_detected": manual_edits_detected,
                "edit_context": edit_context,
                "stories": existing_stories,  # Preserve stories through refinement
                "error": None,
            }

        # Parse as new epic
        project_key = state.get("project_key")
        parsed_epic = self._parse_epic(user_message, project_key=project_key)
        logger.info(f"InputNode: Parsed epic - {parsed_epic.title} (Project: {project_key})")

        return {
            "epic_input": user_message,
            "parsed_epic": parsed_epic,
            "is_first_message": True,
            "refinement_feedback": None,
            "is_save_requested": False,
            "manual_edits_detected": False,
            "edit_context": None,
            "error": None,
        }

    def _is_new_epic_intent(self, text: str, existing_stories: list[UserStory]) -> bool:
        """
        Detect if the user is likely starting a new epic rather than refining.
        Heuristics:
        - High word count (> 20 words)
        - No mention of existing story titles or internal refinement keywords
        - Presence of 'epic' formatting tokens (#, Heading, etc.)
        """
        text_lower = text.lower()
        word_count = len(text.split())

        # If it's short, it's likely feedback
        if word_count < 15:
            return False

        # If it contains specific feedback verbs
        feedback_verbs = ["add", "change", "remove", "update", "modify", "split", "merge", "make", "explain", "why"]
        # Basic check: if it starts with a verb, it's likely feedback
        first_word = text_lower.split()[0] if text_lower.split() else ""
        if first_word in feedback_verbs:
            return False

        # If it mentions 'epic' or has structured layout
        if any(p in text for p in ["# ", "Title:", "Epic:", "Feature:"]):
            return True

        # If it's reasonably long and doesn't look like a command
        if word_count > 30:
            return True

        return False

    def _detect_manual_edits(
        self, incoming_stories: list[Any], existing_stories: list[UserStory]
    ) -> tuple[bool, str | None]:
        """Compare incoming stories with existing ones to detect manual edits."""
        if not existing_stories or not incoming_stories:
            return False, None

        edits = []

        # Create map of existing stories by ID
        existing_map = {s.id: s for s in existing_stories}

        for inc_story_data in incoming_stories:
            if not isinstance(inc_story_data, dict):
                continue

            inc_id = inc_story_data.get("id")
            if not inc_id or inc_id not in existing_map:
                continue

            existing = existing_map[inc_id]

            # Compare fields
            field_changes = []
            if inc_story_data.get("title") != existing.title:
                field_changes.append("title")
            if inc_story_data.get("description") != existing.description:
                field_changes.append("description")

            # Basic AC comparison
            inc_ac = inc_story_data.get("acceptance_criteria", [])

            ac_changed = False
            if len(inc_ac) != len(existing.acceptance_criteria):
                ac_changed = True
            else:
                for i, ac_data in enumerate(inc_ac):
                    # Incoming might be dict or string
                    inc_desc = ac_data.get("description") if isinstance(ac_data, dict) else str(ac_data)
                    if inc_desc != existing.acceptance_criteria[i].description:
                        ac_changed = True
                        break

            if ac_changed:
                field_changes.append("acceptance criteria")

            if field_changes:
                edits.append(f"{inc_id} ({', '.join(field_changes)})")

        if edits:
            context = "Note: The user has manually updated the following stories: " + "; ".join(edits)
            return True, context

        return False, None

    def _is_save_intent(self, text: str) -> bool:
        """Detect if the user wants to save/export to JIRA."""
        keywords = [
            r"save",
            r"push",
            r"export",
            r"create issues",
            r"sync",
            r"finalize",
            r"looks good",
            r"perfect",
            r"send to jira",
        ]
        text_lower = text.lower()
        return any(re.search(kw, text_lower) for kw in keywords)

    def _parse_epic(self, input_text: str, project_key: str | None = None) -> Epic:
        """
        Parse epic from user input.

        Attempts to extract structured information from free-form text.
        """
        # Try to extract title if formatted
        title = self._extract_title(input_text)

        # Try to extract context if mentioned
        context = self._extract_context(input_text)

        # Clean description
        description = input_text.strip()

        return Epic(
            title=title,
            description=description,
            context=context,
            project_key=project_key,
        )

    def _extract_title(self, text: str) -> str:
        """Extract or generate a title from the input."""
        # Check for explicit title patterns
        patterns = [
            r"^#\s*(.+?)[\n\r]",  # Markdown heading
            r"^Title:\s*(.+?)[\n\r]",  # Explicit title
            r"^Epic:\s*(.+?)[\n\r]",  # Epic prefix
            r"^Feature:\s*(.+?)[\n\r]",  # Feature prefix
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()

        # Generate title from first sentence or line
        first_line = text.split("\n")[0].strip()
        if len(first_line) <= 100:
            return first_line

        # Truncate intelligently
        words = first_line.split()
        title_words = []
        char_count = 0
        for word in words:
            if char_count + len(word) > 80:
                break
            title_words.append(word)
            char_count += len(word) + 1

        return " ".join(title_words) + "..."

    def _extract_context(self, text: str) -> str | None:
        """Extract additional context if provided."""
        patterns = [
            r"Context:\s*(.+?)(?:\n\n|\Z)",
            r"Background:\s*(.+?)(?:\n\n|\Z)",
            r"Tech Stack:\s*(.+?)(?:\n\n|\Z)",
            r"Constraints:\s*(.+?)(?:\n\n|\Z)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None


# Convenience function for standalone testing
async def input_node(state: BacklogAgentState) -> dict[str, Any]:
    """Functional wrapper for InputNode."""
    node = InputNode()
    return await node(state)
