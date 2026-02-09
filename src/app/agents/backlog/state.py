"""
Backlog Agent State
===================
TypedDict defining the state that flows through the LangGraph workflow.
Each node can read and update specific fields of this state.
"""

from typing import Any

from ...agents.base import BaseAgentState
from .schemas import DecompositionResult, Epic, UserStory


class BacklogAgentState(BaseAgentState):
    """
    The state object that flows through the Backlog Assistant graph.

    Attributes:
        messages: Conversation history for multi-turn refinement
        epic_input: The original epic/feature description from user
        parsed_epic: Structured epic after parsing
        stories: List of decomposed user stories
        current_result: The full decomposition result
        refinement_feedback: User's feedback for the current turn
        is_first_message: Whether this is the initial decomposition
        output_format: Target format (json, markdown, jira)
        story_template: Preferred story template (standard, bdd, minimal)
        export_result: JIRA export status (if triggered)
        thread_id: Conversation thread identifier
        tenant_id: Multi-tenant isolation identifier
        project_key: JIRA project key associated with this thread
        error: Error message if something failed
        manual_edits_detected: Whether user manually edited stories
        edit_context: Context of manual edits
        usage_metadata: (Inherited) Token usage data
        metadata: (Inherited) Extensibility
    """

    # Core conversation
    messages: list[dict[str, Any]]
    epic_input: str
    parsed_epic: Epic | None

    # Decomposition output
    stories: list[UserStory]
    current_result: DecompositionResult | None

    # Refinement flow
    refinement_feedback: str | None
    is_first_message: bool
    is_save_requested: bool | None

    # Output configuration
    output_format: str
    story_template: str
    formatted_output: str | None
    summary: str | None  # Primary summary for the current turn

    # Export (optional)
    export_result: dict[str, Any] | None

    # Session    # Metadata
    thread_id: str
    tenant_id: str | None
    project_key: str | None
    parent_epic_id: str | None
    user_id: str | None  # Context for audit logging
    error: str | None
    metadata: dict[str, Any]

    # Edit awareness
    manual_edits_detected: bool
    edit_context: str | None
    is_locked: bool | None

    # Intent Classification (Phase 1)
    detected_intent: str | None
    target_issue_type: str | None  # Requested issue type for export (Story, Task, etc.)

    # Help/Q&A (Phase 2)
    help_response: str | None

    # View/Identify (Phase 14)
    view_response: str | None

    # Grooming (Phase 4)
    grooming_report: dict | None

    # Entity Extraction (Phase 5)
    extracted_entities: list | None  # Extracted Jira entities
    enriched_context: str | None  # Formatted context from Jira
    auto_bound_project: str | None  # Project key from first entity
    auto_bound_epic: str | None  # Epic key from entity or parent
