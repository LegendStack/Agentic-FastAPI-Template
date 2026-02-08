"""
Demo Agent State
================
TypedDict defining the state that flows through the LangGraph workflow.
Each node can read and update this state.
"""

from typing import Any

from typing_extensions import TypedDict


class DemoAgentState(TypedDict):
    """
    The state object that flows through the agent graph.

    Attributes:
        messages: Conversation history (list of {role, content} dicts)
        original_input: The raw user input before any processing
        sanitized_input: Input after PII masking
        context: Retrieved documents/knowledge
        entities: Extracted entities from the conversation
        response: The generated response
        reflection: Self-correction feedback (if any)
        needs_human_approval: Flag for HITL
        human_approved: Whether human has approved
        cost_info: Token usage and cost tracking
        cache_hit: Whether response came from cache
        tenant_id: Multi-tenant isolation identifier
        thread_id: Conversation thread identifier
        metadata: Arbitrary metadata for extensibility
    """

    # Core conversation
    messages: list[dict[str, Any]]
    original_input: str
    sanitized_input: str

    # RAG context
    context: str
    entities: list[dict[str, Any]]

    # Generation
    response: str
    reflection: dict[str, Any] | None

    # Governance
    needs_human_approval: bool
    human_approved: bool

    # Observability
    cost_info: dict[str, Any]
    cache_hit: bool

    # Multi-tenancy
    tenant_id: str | None
    thread_id: str

    # Extensibility
    metadata: dict[str, Any]
