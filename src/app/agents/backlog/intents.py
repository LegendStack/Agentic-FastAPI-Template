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
    """Generic decomposition (default to stories)."""

    DECOMPOSE_TO_EPICS = "decompose_to_epics"
    """Decompose a high-level requirement or document into multiple epics."""

    DECOMPOSE_TO_STORIES = "decompose_to_stories"
    """Decompose an epic or feature into multiple user stories (with parent linking)."""

    DECOMPOSE_TO_TASKS = "decompose_to_tasks"
    """Decompose a user story into technical implementation tasks."""

    DECOMPOSE_TO_SUBTASKS = "decompose_to_subtasks"
    """Decompose a task into granular sub-tasks."""

    REFINE = "refine"
    """Improve, modify, or enhance existing stories in the backlog."""

    ENHANCE = "enhance"
    """Enhance a specific story with targeted improvements (ACs, edge cases, BDD)."""

    HELP = "help"
    """Answer questions, explain capabilities, or provide guidance."""

    GROOM = "groom"
    """Analyze backlog for duplicates, dependencies, or quality issues."""

    VIEW = "view"
    """Retrieve and display details for a specific entity without decomposing it."""

    ESTIMATE = "estimate"
    """Provide story point estimates or effort analysis. (Future)"""

    UNKNOWN = "unknown"
    """Fallback when intent cannot be determined."""


# Descriptions used for zero-shot classification prompts
INTENT_DESCRIPTIONS: dict[UserIntent, str] = {
    UserIntent.DECOMPOSE: (
        "User wants to break down a requirement into smaller items. Defaults to user stories if level not specified."
    ),
    UserIntent.DECOMPOSE_TO_EPICS: (
        "User wants to decompose a high-level requirements document or charter into multiple Epics. "
        "Keywords: 'into epics', 'list of epics', 'breakdown into epics'."
    ),
    UserIntent.DECOMPOSE_TO_STORIES: (
        "User wants to decompose an Epic into User Stories. "
        "Keywords: 'into stories', 'user stories for', 'breakdown this epic'."
    ),
    UserIntent.DECOMPOSE_TO_TASKS: (
        "User wants to decompose a User Story into technical tasks. "
        "Keywords: 'into tasks', 'technical tasks', 'breakdown this story'."
    ),
    UserIntent.DECOMPOSE_TO_SUBTASKS: (
        "User wants to decompose a Task into Sub-tasks. "
        "Keywords: 'into sub-tasks', 'subtasks', 'breakdown this task'."
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
    UserIntent.VIEW: (
        "User wants to view, identify, or see details for a specific Jira entity or story. "
        "They are asking 'what is this' or 'identify this' rather than wanting to break it down."
    ),
    UserIntent.ESTIMATE: ("User wants story point estimates, effort analysis, or complexity evaluation. (Future)"),
}


def get_intent_classification_prompt() -> str:
    """
    Generate the system prompt for intent classification.

    Returns:
        System prompt instructing the LLM to classify user intent.
    """
    intent_list = "\n".join(
        f"- **{intent.value}**: {desc}" for intent, desc in INTENT_DESCRIPTIONS.items() if intent != UserIntent.UNKNOWN
    )

    return f"""You are an intent classifier for a Backlog Assistant agent.

Your task is to analyze the user's message and classify their intent into ONE of these categories:

{intent_list}

## Rules:
1. If the user provides substantial content to be broken down, classify as the most appropriate "decompose_to_*" intent. 
   - Use "decompose_to_epics" for high-level docs/charters.
   - Use "decompose_to_stories" for specific features or epics.
   - Use "decompose_to_tasks" for specific user stories.
   - Use "decompose_to_subtasks" for specific tasks.
   - Fallback to "decompose" if ambiguous.
2. If the user references existing stories and wants changes, classify as "refine"
3. If the user asks questions, greetings, or seeks help, classify as "help"
4. If the user wants to simply view or identify a specific story or entity, classify as "view"
5. If the user wants analysis of the backlog (duplicates, dependencies), classify as "groom"
6. When in doubt, prefer "help" over incorrectly triggering a workflow

## Output:
Respond with ONLY the intent value (lowercase): decompose, decompose_to_epics, decompose_to_stories, decompose_to_tasks, decompose_to_subtasks, refine, enhance, help, view, groom, or estimate
Do not include any other text."""


def get_valid_intents() -> list[str]:
    """Get list of valid intent values for parsing."""
    return [intent.value for intent in UserIntent if intent != UserIntent.UNKNOWN]
