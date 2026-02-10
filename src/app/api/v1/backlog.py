"""
Backlog Assistant API Routes
============================
REST API endpoints for the Story Decomposition Agent.

Endpoints:
- POST /backlog/decompose - Start epic decomposition
- POST /backlog/refine - Refine existing stories (Door B)
- POST /backlog/chat/{thread_id} - Conversational refinement
- GET /backlog/stories/{thread_id} - Get current decomposition
- POST /backlog/export/{thread_id} - Export to JIRA
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents.backlog.config import BacklogAgentConfig
from ...agents.backlog.nodes.import_node import ImportNode
from ...agents.backlog.schemas import UserStory
from ...agents.persistence import SqlAlchemyCheckpointSaver
from ...api.dependencies import get_optional_user
from ...core.db.database import async_get_db
from ...models.user import User

router = APIRouter(prefix="/backlog", tags=["backlog"])


# === Request/Response Models ===


class DecomposeRequest(BaseModel):
    """Request body for epic decomposition."""

    epic_description: str = Field(
        ...,
        description="The epic or feature description to decompose",
        min_length=10,
        max_length=10000,
        examples=["Add SSO login support for enterprise customers"],
    )
    context: str | None = Field(
        None,
        description="Additional context (tech stack, constraints, etc.)",
        examples=["We use Azure AD as our IdP. Need SAML and OIDC support."],
    )
    output_format: Literal["json", "markdown", "jira"] = Field(
        "json",
        description="Desired output format",
    )
    story_template: Literal["standard", "bdd", "minimal"] = Field(
        "standard",
        description="Story format template",
    )
    enable_edge_cases: bool = Field(
        True,
        description="Include edge case scenarios",
    )
    enable_complexity_estimation: bool = Field(
        True,
        description="Add T-shirt size estimates",
    )
    parent_epic_id: str | None = Field(
        None,
        description="Optional JIRA Epic ID to link stories to",
    )


class ChatRequest(BaseModel):
    """
    Request body for unified chat interactions.

    This is the primary request model for the /chat endpoint.
    The agent internally classifies intent and routes appropriately.
    """

    message: str = Field(
        ...,
        description="User message (query, epic description, or refinement feedback)",
        min_length=1,
        max_length=10000,
        examples=[
            "Add more edge cases for the authentication stories",
            "Show me details for PDLC-24",
            "How can you help me?",
        ],
    )
    thread_id: str | None = Field(
        None,
        description="Optional thread ID to continue an existing conversation",
    )
    project_key: str | None = Field(
        None,
        description="Optional JIRA project key to scope operations",
    )
    output_format: Literal["json", "markdown", "jira"] | None = Field(
        None,
        description="Override output format for this message",
    )
    stories: list[UserStory] | None = Field(
        None,
        description="Optional: Inject existing stories (for 'Door B' refinement)",
    )
    parent_epic_id: str | None = Field(
        None,
        description="Optional JIRA Epic ID to link stories to",
    )


# StoryResponse is now unified with UserStory for strict type symmetry


class DecomposeResponse(BaseModel):
    """Response model for chat/decomposition result."""

    thread_id: str = ""  # May be empty for VIEW/HELP flows
    story_count: int = 0  # Zero for non-decompose flows
    summary: str | None = None
    output_format: str = "json"
    stories: list[UserStory] = []
    formatted_output: str | None = None
    recommendations: list[str] = []
    error: str | None = None
    usage: dict[str, Any] | None = None
    jira_base_url: str | None = None
    is_locked: bool = False
    target_level: str | None = "story"
    target_issue_type: str | None = "Story"


class RefineRequest(BaseModel):
    """Request body for existing story refinement (Door B)."""

    stories: list[UserStory] = Field(
        ...,
        description="List of existing stories to refine",
    )
    message: str = Field(
        ...,
        description="Refinement feedback or instructions",
        examples=["Convert these stories to BDD format"],
    )
    thread_id: str | None = Field(
        None,
        description="Optional thread ID if continuing a session",
    )
    output_format: Literal["json", "markdown", "jira"] | None = Field(
        None,
        description="Override output format",
    )
    parent_epic_id: str | None = Field(
        None,
        description="Optional JIRA Epic ID to link stories to",
    )


class ExportRequest(BaseModel):
    """Request body for JIRA export."""

    project_key: str | None = Field(
        None,
        description="JIRA project key (uses default if not provided)",
    )


class ExportResponse(BaseModel):
    """Response model for JIRA export result."""

    thread_id: str
    status: str
    message: str
    issues: list[dict] | None = None
    stories: list[UserStory] | None = None
    errors: list[dict] | None = None
    is_locked: bool = False
    error: str | None = None


# === Helper Functions ===


def get_agent(
    db: AsyncSession,
    config: BacklogAgentConfig | None = None,
) -> Any:
    """
    Create a BacklogAssistantAgent with database persistence and Jira integration.

    This function now creates a JiraService instance and injects it into the agent,
    enabling proper dependency injection for Jira operations.
    """
    from ...agents.backlog import BacklogAssistantAgent
    from ...services.jira_service import JiraConfig, JiraConfigurationError, JiraService

    checkpointer = SqlAlchemyCheckpointSaver(db)

    # Create JiraService for dependency injection
    jira_service = None
    try:
        jira_config = JiraConfig.from_settings()
        if jira_config.is_configured:
            jira_service = JiraService(jira_config)
    except JiraConfigurationError:
        # Jira not configured - agent will work without Jira features
        pass

    return BacklogAssistantAgent(
        config=config,
        checkpointer=checkpointer,
        jira_service=jira_service,
    )


# === API Endpoints ===


@router.post("/import", response_model=DecomposeRequest)
async def import_file(
    file: UploadFile = File(...),
) -> DecomposeRequest:
    """
    Import a file (PDF, Docx, TXT) and convert to epic description.
    """
    node = ImportNode()
    # Read into memory or pass file object
    # unstructured partition expects file-like or filename
    text = node.parse_file(file.file, file.filename)

    # Heuristic cleanup: limit to first 5000 chars if too long
    if len(text) > 10000:
        text = text[:10000] + "\n\n... (truncated)"

    return DecomposeRequest(epic_description=text, output_format="json")


@router.post("/chat", response_model=DecomposeResponse)
async def chat_handler(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
    current_user: Annotated[User, Depends(get_optional_user)] = None,
) -> DecomposeResponse:
    """
    Unified chat endpoint for all Backlog Assistant interactions.

    This is the primary entry point for the agent. It handles:
    - **DECOMPOSE**: Epic descriptions → user stories
    - **VIEW**: Jira entity queries (e.g., "show me PDLC-24")
    - **HELP**: Capability questions (e.g., "what can you do?")
    - **REFINE**: Story improvement requests
    - **GROOM**: Backlog analysis
    - **ENHANCE**: Story detail additions

    The agent internally classifies intent and routes to the appropriate handler.
    """
    config = BacklogAgentConfig(
        DEFAULT_OUTPUT_FORMAT=request.output_format or "json",
        USE_MOCKS=False,
    )

    try:
        agent = get_agent(db, config=config)
        user_id = str(current_user.id) if current_user else "anonymous"

        # Generate thread_id for new conversations
        import uuid

        thread_id = request.thread_id or str(uuid.uuid4())

        # Use the chat method which runs the full graph with intent classification
        result = await agent.chat(
            thread_id=thread_id,  # Required first positional arg
            message=request.message,
            project_key=request.project_key,
            parent_epic_id=request.parent_epic_id,
            user_id=user_id,
            output_format=request.output_format,
            initial_stories=request.stories,
        )

        if result.get("error"):
            return DecomposeResponse(
                thread_id=result.get("thread_id", ""),
                story_count=0,
                summary=result.get("summary"),
                output_format=request.output_format or "json",
                stories=[],
                error=result["error"],
            )

        # Save metadata (project_key) if available
        if request.project_key:
            from ...agents.conversations import ConversationService
            conversation_service = ConversationService(db)
            await conversation_service.update_metadata(result["thread_id"], {"project_key": request.project_key})

        from ...core.config import settings

        return DecomposeResponse(
            thread_id=result.get("thread_id", ""),
            story_count=result.get("story_count", 0),
            summary=result.get("summary"),
            output_format=result.get("output_format", "json"),
            stories=result.get("stories", []),
            formatted_output=result.get("formatted_output"),
            recommendations=result.get("recommendations", []),
            error=result.get("error"),
            usage=result.get("usage"),
            jira_base_url=settings.JIRA_URL,
            is_locked=result.get("is_locked", False),
            target_level=result.get("target_level", "story"),
            target_issue_type=result.get("target_issue_type", "Story"),
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/decompose", response_model=DecomposeResponse)
async def decompose_epic(
    request: DecomposeRequest,
    project_key: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
    current_user: Annotated[User, Depends(get_optional_user)] = None,
) -> DecomposeResponse:
    """
    Takes a high-level epic description and breaks it down into
    well-structured user stories with acceptance criteria.

    Returns a thread_id that can be used for subsequent refinement.
    """
    config = BacklogAgentConfig(
        STORY_TEMPLATE=request.story_template,
        DEFAULT_OUTPUT_FORMAT=request.output_format,
        ENABLE_EDGE_CASES=request.enable_edge_cases,
        ENABLE_COMPLEXITY_ESTIMATION=request.enable_complexity_estimation,
        USE_MOCKS=False,  # Explicitly disable mocks for the real endpoint
    )

    try:
        agent = get_agent(db, config=config)
        user_id = str(current_user.id) if current_user else "anonymous"

        result = await agent.decompose(
            epic_description=request.epic_description,
            context=request.context,
            output_format=request.output_format,
            project_key=project_key,
            parent_epic_id=request.parent_epic_id,
            user_id=user_id,
        )

        if result.get("error"):
            return DecomposeResponse(
                thread_id=result["thread_id"],
                story_count=0,
                summary=None,
                output_format=request.output_format,
                stories=[],
                error=result["error"],
            )

        # Extract recommendations from full response
        full_response = result.get("response", {})
        recommendations = full_response.get("recommendations", []) if full_response else []

        # Save metadata (project_key) if available
        if project_key:
            from ...agents.conversations import ConversationService
            conversation_service = ConversationService(db)
            await conversation_service.update_metadata(result["thread_id"], {"project_key": project_key})

        from ...core.config import settings

        return DecomposeResponse(
            thread_id=result["thread_id"],
            story_count=result.get("story_count", 0),
            summary=result.get("summary"),
            output_format=result.get("output_format", "json"),
            stories=result.get("stories", []),
            formatted_output=result.get("formatted_output"),
            recommendations=recommendations,
            error=result.get("error"),
            usage=result.get("usage"),
            jira_base_url=settings.JIRA_URL,
            is_locked=result.get("is_locked", False),
            target_level=result.get("target_level", "story"),
            target_issue_type=result.get("target_issue_type", "Story"),
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug Error Decompose: {str(e)}")


@router.post("/chat/{thread_id}", response_model=DecomposeResponse)
async def refine_decomposition(
    thread_id: str,
    request: ChatRequest,
    project_key: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
    current_user: Annotated[User, Depends(get_optional_user)] = None,
) -> DecomposeResponse:
    """
    Refine an existing decomposition or start refinement from existing stories.

    This unified endpoint supports:
    1. **Continuation**: Send feedback for stories already in the thread.
    2. **Hydration (Door B)**: Send a list of `stories` in the first message to initialize refinement.
    """
    config = BacklogAgentConfig(USE_MOCKS=False)

    try:
        agent = get_agent(db, config=config)
        user_id = str(current_user.id) if current_user else "anonymous"

        result = await agent.chat(
            thread_id=thread_id,
            message=request.message,
            output_format=request.output_format,
            initial_stories=request.stories,
            project_key=project_key,
            parent_epic_id=request.parent_epic_id,
            user_id=user_id,  # Inject user_id
        )

        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])

        # Extract recommendations from full response
        full_response = result.get("response", {})
        recommendations = full_response.get("recommendations", []) if full_response else []

        return DecomposeResponse(
            thread_id=result["thread_id"],
            story_count=result.get("story_count", 0),
            summary=result.get("summary"),
            output_format=result.get("output_format", "json"),
            stories=result.get("stories", []),
            formatted_output=result.get("formatted_output"),
            recommendations=recommendations,
            error=result.get("error"),
            usage=result.get("usage"),
            is_locked=result.get("is_locked", False),
            target_level=result.get("target_level", "story"),
            target_issue_type=result.get("target_issue_type", "Story"),
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug Error Chat: {str(e)}")


@router.get("/stories/{thread_id}")
async def get_stories(
    thread_id: str,
    checkpoint_id: str | None = None,
    output_format: Literal["json", "markdown"] = "json",
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict:
    """
    Get the current decomposition for a thread.

    Returns all stories and the full decomposition result.
    If checkpoint_id is provided, returns that specific version.
    """
    try:
        agent = get_agent(db)

        if checkpoint_id:
            result = await agent.get_stories_at_version(thread_id, checkpoint_id)
        else:
            result = await agent.get_stories(thread_id)

        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])

        # Format output if markdown requested
        if output_format == "markdown" and result.get("result"):
            from ...agents.backlog.schemas import DecompositionResult

            decomp = DecompositionResult.model_validate(result["result"])
            result["formatted_output"] = decomp.to_markdown()

        # Fetch rich message history from DB if available
        messages = []
        if hasattr(agent.checkpointer, "db"):
            try:
                from ...agents.conversations import ConversationService

                conversation_service = ConversationService(agent.checkpointer.db)
                db_messages = await conversation_service.get_messages(thread_id, limit=50)

                # Convert DB messages to dicts
                messages = [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "timestamp": (m.created_at.timestamp() * 1000) if m.created_at else None,
                        "input_tokens": m.input_tokens,
                        "output_tokens": m.output_tokens,
                    }
                    for m in db_messages
                ]
            except Exception as e:
                # Log error but fallback to simple state
                print(f"Error fetching DB messages: {e}")
                messages = []

        # Fallback to state messages if DB is empty (e.g. non-persistent mode)
        if not messages and result.get("messages"):
            messages = result.get("messages", [])

        # Return combined result
        # Note: stories and result are already processed (model_dumped) by agent.get_stories if needed
        return {
            "thread_id": thread_id,
            "stories": result.get("stories", []),
            "result": result.get("result"),
            "messages": messages,
            "is_locked": result.get("is_locked", False),
            "metadata": result.get("metadata", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug Error: {str(e)}")


@router.get("/history/{thread_id}")
async def get_thread_history(
    thread_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict:
    """
    Get the state history for a thread.

    Returns a list of available checkpoints (versions) with timestamps
    and basic summaries to power the Artifact version selector.
    """
    agent = get_agent(db)
    config = {"configurable": {"thread_id": thread_id}}

    versions = []
    async for state in agent.graph.aget_state_history(config):
        # Only include terminal states (completed turns) to avoid version clutter
        if state.next or not state.values or "stories" not in state.values:
            continue

        current_result = state.values.get("current_result")
        summary = "Initial Decomposition"
        if isinstance(current_result, dict):
            summary = current_result.get("summary", "Refinement Step")
        elif hasattr(current_result, "summary"):
            summary = current_result.summary

        versions.append(
            {
                "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id"),
                "timestamp": state.created_at if hasattr(state, "created_at") else None,
                "summary": summary[:100] + ("..." if len(summary) > 100 else ""),
                "story_count": len(state.values.get("stories", [])),
                # Metadata to help frontend identify the trigger
                "is_refinement": not state.values.get("is_first_message", True),
            }
        )

    return {"thread_id": thread_id, "versions": versions}


@router.post("/refine", response_model=DecomposeResponse)
async def refine_existing_stories(
    request: RefineRequest,
    project_key: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
    current_user: Annotated[User, Depends(get_optional_user)] = None,
) -> DecomposeResponse:
    """
    Refine existing stories based on user feedback.

    Directly injects existing stories into the agent state and
    processes the feedback message. This is the "Door B" entry point.
    """
    config = BacklogAgentConfig(USE_MOCKS=False)
    agent = get_agent(db, config)

    thread_id = request.thread_id or str(uuid.uuid4())
    user_id = str(current_user.id) if current_user else "anonymous"

    result = await agent.chat(
        thread_id=thread_id,
        message=request.message,
        output_format=request.output_format,
        initial_stories=request.stories,
        project_key=project_key,
        parent_epic_id=request.parent_epic_id,
        user_id=user_id,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    full_response = result.get("response", {})
    recommendations = full_response.get("recommendations", []) if full_response else []

    return DecomposeResponse(
        thread_id=result["thread_id"],
        story_count=result.get("story_count", 0),
        summary=result.get("summary"),
        output_format=result.get("output_format", "json"),
        stories=result.get("stories", []),
        formatted_output=result.get("formatted_output"),
        recommendations=recommendations,
        error=result.get("error"),
        usage=result.get("usage"),
        is_locked=result.get("is_locked", False),
    )


@router.post("/export/{thread_id}", response_model=ExportResponse)
async def export_to_jira(
    thread_id: str,
    request: ExportRequest | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
    current_user: Annotated[User, Depends(get_optional_user)] = None,
) -> ExportResponse:
    """
    Export the decomposition to JIRA.

    Creates JIRA issues for each user story in the decomposition.
    Requires JIRA configuration (JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN).

    Note: By default, JIRA export uses mock mode for safety.
    Set USE_MOCKS=False in configuration for real exports.
    """
    config = BacklogAgentConfig(
        ENABLE_JIRA_EXPORT=True,
        JIRA_PROJECT_KEY=request.project_key if request else None,
        USE_MOCKS=False,
    )

    agent = get_agent(db, config)
    user_id = str(current_user.id) if current_user else "anonymous"

    result = await agent.save_to_jira(thread_id, user_id=user_id)

    if result.get("error") and not result.get("export_result"):
        raise HTTPException(status_code=400, detail=result["error"])

    export_result = result.get("export_result", {})
    if export_result.get("status") == "error":
        raise HTTPException(status_code=400, detail=export_result.get("message", "Export failed"))

    return ExportResponse(
        thread_id=thread_id,
        status=export_result.get("status", "error"),
        message=export_result.get("message", "Unknown error"),
        issues=export_result.get("issues"),
        stories=result.get("stories"),
        errors=export_result.get("errors"),
        is_locked=result.get("is_locked", False),
        error=result.get("error"),
    )


@router.get("/config")
async def get_agent_config() -> dict:
    """
    Get the default agent configuration.

    Useful for understanding available options and current defaults.
    """
    from ...agents.backlog import BacklogAssistantAgent

    agent = BacklogAssistantAgent()
    return agent.get_config_summary()
