"""
Input Node
==========
Parses and validates the incoming epic description.
Determines if this is a new decomposition or a refinement request.
"""

import logging
import re
from typing import Any

from ..schemas import Epic
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

        # Validate input length
        if len(user_message) < self.MIN_INPUT_LENGTH:
            return {
                "error": f"Input too short. Please provide at least {self.MIN_INPUT_LENGTH} characters describing the epic."
            }

        if len(user_message) > self.MAX_INPUT_LENGTH:
            user_message = user_message[: self.MAX_INPUT_LENGTH]
            logger.warning(f"InputNode: Input truncated to {self.MAX_INPUT_LENGTH} characters")

        # Determine if this is a new decomposition or refinement
        is_first_message = state.get("is_first_message", True)
        existing_stories = state.get("stories", [])

        if existing_stories and not is_first_message:
            # This is a refinement request
            logger.info("InputNode: Detected refinement request")
            return {
                "refinement_feedback": user_message,
                "is_first_message": False,
                "error": None,
            }

        # Parse as new epic
        parsed_epic = self._parse_epic(user_message)
        logger.info(f"InputNode: Parsed epic - {parsed_epic.title}")

        return {
            "epic_input": user_message,
            "parsed_epic": parsed_epic,
            "is_first_message": True,
            "refinement_feedback": None,
            "error": None,
        }

    def _parse_epic(self, input_text: str) -> Epic:
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
