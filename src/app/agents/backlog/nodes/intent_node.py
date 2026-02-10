"""
Intent Classification Node
===========================
Classifies user messages into intents to determine the appropriate workflow path.
This node runs early in the graph to enable intelligent routing.
"""

import logging
from typing import Any

from ...azure_openai import LLMService
from ..intents import UserIntent, get_intent_classification_prompt, get_valid_intents
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class IntentNode:
    """
    Node that classifies user intent using LLM.

    This node analyzes the user's message and determines their intent,
    which is then used by the routing logic to select the appropriate
    workflow path (decompose, refine, help, groom, etc.).
    """

    def __init__(self, llm: LLMService):
        """
        Initialize the Intent Classification Node.

        Args:
            llm: The LLM service instance to use for classification.
        """
        self.llm = llm
        self._system_prompt = get_intent_classification_prompt()
        self._valid_intents = get_valid_intents()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Classify the user's intent based on their message.

        Args:
            state: Current agent state containing the user message.

        Returns:
            Updated state with detected_intent field.
        """
        # Get the latest user message from history first (most reliable for current turn)
        messages = state.get("messages", [])
        user_message = ""

        if messages:
            for msg in reversed(messages):
                if msg.get("role") in ["user", "human"]:
                    user_message = msg.get("content", "")
                    break

        # Fallback to epic_input if no messages found
        if not user_message:
            user_message = state.get("epic_input") or ""

        if not user_message:
            logger.warning("IntentNode: No user message found, defaulting to HELP")
            return {"detected_intent": UserIntent.HELP.value}

        # Check for existing stories - if they exist and user isn't providing new content,
        # they're likely refining
        has_stories = bool(state.get("stories"))
        is_first = state.get("is_first_message", True)
        # Entity awareness
        entities = state.get("extracted_entities", [])
        has_entities = len(entities) > 0

        lower_message = user_message.lower().strip()

        logger.info(
            f"IntentNode: Checking message='{user_message[:50]}...' "
            f"is_first={is_first} has_stories={has_stories} has_entities={has_entities}"
        )

        # Help indicators - CHECK FIRST before any other logic
        help_patterns = [
            "help",
            "how can you",
            "what can you",
            "what do you",
            "who are you",
            "capabilities",
            "introduce",
            "hello",
            "hi",
            "how does",
            "what is",
            "explain",
        ]

        # Check help patterns with clear logging
        # If we have entities, we should be more skeptical of help patterns (could be 'what is this story')
        for pattern in help_patterns:
            if pattern in lower_message:
                logger.info(f"IntentNode: Found help pattern '{pattern}' in message, len={len(user_message)}")
                if not has_entities and len(user_message) < 100:
                    logger.info("IntentNode: Quick match for HELP intent - returning help")
                    return {"detected_intent": UserIntent.HELP.value}
                elif has_entities:
                    logger.info(
                        "IntentNode: Help pattern found but entities present, deferring to LLM or further logic"
                    )
                else:
                    logger.info(f"IntentNode: Message too long ({len(user_message)} >= 100), skipping help")
                break

        # Groom indicators
        groom_patterns = [
            "duplicate",
            "duplicates",
            "dependency",
            "dependencies",
            "analyze",
            "quality",
            "missing",
            "gaps",
            "overlap",
            "groom",
            "grooming",
            "review backlog",
            "check backlog",
            "audit",
            "assess",
            "evaluate",
        ]

        # View/Identity indicators
        view_patterns = [
            "identify",
            "identity",
            "show me",
            "what is",
            "details for",
            "view",
            "get details",
            "describe story",
            "lookup",
            "who is working",
            "status of",
        ]

        groom_match = any(pattern in lower_message for pattern in groom_patterns)
        view_match = any(pattern in lower_message for pattern in view_patterns)

        logger.info(
            f"IntentNode: Heuristics - groom={groom_match}, view={view_match}, "
            f"has_stories={has_stories}, entities={has_entities}"
        )

        # View Intent (Retrieve details without decomposition)
        # PRIORITY: If user specifically asks to identify/view OR it's a very short query with entities
        if view_match or (has_entities and len(user_message) < 60):
            logger.info("IntentNode: Quick match for VIEW intent")
            return {"detected_intent": UserIntent.VIEW.value}

        if groom_match and has_stories:
            logger.info("IntentNode: Quick match for GROOM intent")
            return {"detected_intent": UserIntent.GROOM.value}

        # If not first and has stories, likely refine (general)
        if not is_first and has_stories:
            logger.info("IntentNode: Has stories and not first message, defaulting to REFINE")
            return {"detected_intent": UserIntent.REFINE.value}

        # Use LLM for ambiguous cases
        try:
            messages = [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Classify this message:\n\n{user_message}"},
            ]

            response = await self.llm.chat(messages)
            raw_intent = response.content.strip().lower()

            # Parse the response
            if raw_intent in self._valid_intents:
                logger.info(f"IntentNode: LLM classified as {raw_intent}")
                return {"detected_intent": raw_intent}
            else:
                # Try to extract intent from response
                for valid in self._valid_intents:
                    if valid in raw_intent:
                        logger.info(f"IntentNode: Extracted {valid} from LLM response")
                        return {"detected_intent": valid}

                logger.warning(f"IntentNode: Could not parse LLM response '{raw_intent}', defaulting to HELP")
                return {"detected_intent": UserIntent.HELP.value}

        except Exception as e:
            logger.error(f"IntentNode: LLM classification failed: {e}")
            # Fallback logic
            if is_first:
                return {"detected_intent": UserIntent.DECOMPOSE.value}
            elif has_stories:
                return {"detected_intent": UserIntent.REFINE.value}
            else:
                return {"detected_intent": UserIntent.HELP.value}
