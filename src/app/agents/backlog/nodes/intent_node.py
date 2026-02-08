"""
Intent Classification Node
===========================
Classifies user messages into intents to determine the appropriate workflow path.
This node runs early in the graph to enable intelligent routing.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

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
    
    def __init__(self, llm: Any):
        """
        Initialize the Intent Classification Node.
        
        Args:
            llm: The language model to use for classification.
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
        # Get the user's message
        user_message = state.get("epic_input") or ""
        if not user_message:
            messages = state.get("messages", [])
            if messages:
                # Get the last human message
                for msg in reversed(messages):
                    if msg.get("role") == "human":
                        user_message = msg.get("content", "")
                        break
        
        if not user_message:
            logger.warning("IntentNode: No user message found, defaulting to HELP")
            return {"detected_intent": UserIntent.HELP.value}
        
        # Check for existing stories - if they exist and user isn't providing new content,
        # they're likely refining
        has_stories = bool(state.get("stories"))
        is_first = state.get("is_first_message", True)
        
        # Quick heuristics for common cases (avoid LLM call when obvious)
        lower_message = user_message.lower().strip()
        
        # Help indicators
        help_patterns = [
            "help", "how can you", "what can you", "what do you",
            "who are you", "capabilities", "introduce", "hello", "hi",
            "how does", "what is", "explain"
        ]
        if any(pattern in lower_message for pattern in help_patterns) and len(user_message) < 100:
            logger.info("IntentNode: Quick match for HELP intent")
            return {"detected_intent": UserIntent.HELP.value}
        
        # Groom indicators
        groom_patterns = [
            "duplicate", "duplicates", "dependency", "dependencies",
            "analyze backlog", "quality", "missing", "gaps", "overlap"
        ]
        if any(pattern in lower_message for pattern in groom_patterns) and has_stories:
            logger.info("IntentNode: Quick match for GROOM intent")
            return {"detected_intent": UserIntent.GROOM.value}
        
        # If first message with substantial content, likely decompose
        if is_first and len(user_message) > 50:
            logger.info("IntentNode: First message with content, defaulting to DECOMPOSE")
            return {"detected_intent": UserIntent.DECOMPOSE.value}
        
        # Enhance indicators - specific story mentioned with enhancement request
        enhance_patterns = [
            "story 1", "story 2", "story 3", "story-", "#1", "#2", "#3",
            "first story", "second story", "third story",
            "add acceptance", "add edge case", "add bdd", "add technical",
            "enhance story", "improve story", "update story"
        ]
        if has_stories and any(pattern in lower_message for pattern in enhance_patterns):
            logger.info("IntentNode: Quick match for ENHANCE intent (specific story)")
            return {"detected_intent": UserIntent.ENHANCE.value}
        
        # If not first and has stories, likely refine (general)
        if not is_first and has_stories:
            logger.info("IntentNode: Has stories and not first message, defaulting to REFINE")
            return {"detected_intent": UserIntent.REFINE.value}
        
        # Use LLM for ambiguous cases
        try:
            messages = [
                SystemMessage(content=self._system_prompt),
                HumanMessage(content=f"Classify this message:\n\n{user_message}")
            ]
            
            response = await self.llm.ainvoke(messages)
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
