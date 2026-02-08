"""
User Intent Enumeration
=======================
Defines the possible intents for the Backlog Assistant agent.
Used by the Intent Classification Node to route user messages.
"""

from enum import Enum


class UserIntent(str, Enum):
    """
    Enum representing the possible user intents.
    
    The agent classifies incoming messages into one of these intents
    to determine the appropriate workflow path.
    """
    
    DECOMPOSE = "decompose"
    """Break down an epic, feature, or requirement into user stories."""
    
    REFINE = "refine"
    """Improve, modify, or enhance existing stories in the backlog."""
    
    ENHANCE = "enhance"
    """Enhance a specific story with targeted improvements (ACs, edge cases, BDD)."""
    
    HELP = "help"
    """Answer questions, explain capabilities, or provide guidance."""
    
    GROOM = "groom"
    """Analyze backlog for duplicates, dependencies, or quality issues."""
    
    ESTIMATE = "estimate"
    """Provide story point estimates or effort analysis. (Future)"""
    
    UNKNOWN = "unknown"
    """Fallback when intent cannot be determined."""


# Descriptions used for zero-shot classification prompts
INTENT_DESCRIPTIONS: dict[UserIntent, str] = {
    UserIntent.DECOMPOSE: (
        "User wants to break down an epic, feature, or requirement into user stories. "
        "They are providing new content to be decomposed, not asking about existing stories."
    ),
    UserIntent.REFINE: (
        "User wants to improve, modify, add details to, or enhance ALL existing user stories. "
        "They are giving general feedback about stories that already exist in the current session."
    ),
    UserIntent.ENHANCE: (
        "User wants to enhance a SPECIFIC story with targeted improvements. "
        "They mention a story by number, ID, or title and want to add ACs, edge cases, BDD, or tech notes."
    ),
    UserIntent.HELP: (
        "User is asking a question, seeking guidance, asking about capabilities, "
        "or wants to understand how the assistant works. They are NOT providing work content."
    ),
    UserIntent.GROOM: (
        "User wants to analyze the current backlog for issues like duplicates, "
        "missing dependencies, quality gaps, or prioritization recommendations."
    ),
    UserIntent.ESTIMATE: (
        "User wants story point estimates, effort analysis, or complexity evaluation. (Future)"
    ),
}


def get_intent_classification_prompt() -> str:
    """
    Generate the system prompt for intent classification.
    
    Returns:
        System prompt instructing the LLM to classify user intent.
    """
    intent_list = "\n".join(
        f"- **{intent.value}**: {desc}"
        for intent, desc in INTENT_DESCRIPTIONS.items()
        if intent != UserIntent.UNKNOWN
    )
    
    return f"""You are an intent classifier for a Backlog Assistant agent.

Your task is to analyze the user's message and classify their intent into ONE of these categories:

{intent_list}

## Rules:
1. If the user provides substantial content (epic description, feature request, requirements), classify as "decompose"
2. If the user references existing stories and wants changes, classify as "refine"
3. If the user asks questions, greetings, or seeks help, classify as "help"
4. If the user wants analysis of the backlog (duplicates, dependencies), classify as "groom"
5. When in doubt, prefer "help" over incorrectly triggering a workflow

## Output:
Respond with ONLY the intent value (lowercase): decompose, refine, help, groom, or estimate
Do not include any other text."""


def get_valid_intents() -> list[str]:
    """Get list of valid intent values for parsing."""
    return [intent.value for intent in UserIntent if intent != UserIntent.UNKNOWN]
