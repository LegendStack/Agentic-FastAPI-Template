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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents.backlog import BacklogAgentConfig
from ...agents.backlog.schemas import UserStory
from ...agents.persistence import SqlAlchemyCheckpointSaver
from ...core.db.database import async_get_db

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


class ChatRequest(BaseModel):
    """Request body for conversational refinement."""

    message: str = Field(
        ...,
        description="User message for refinement",
        min_length=1,
        max_length=5000,
        examples=["Add more edge cases for the authentication stories"],
    )
    output_format: Literal["json", "markdown", "jira"] | None = Field(
        None,
        description="Override output format for this message",
    )
    stories: list[UserStory] | None = Field(
        None,
        description="Optional: Inject existing stories (for 'Door B' refinement)",
    )


# StoryResponse is now unified with UserStory for strict type symmetry


class DecomposeResponse(BaseModel):
    """Response model for decomposition result."""

    thread_id: str
    story_count: int
    summary: str | None
    output_format: str
    stories: list[UserStory]
    formatted_output: str | None = None
    recommendations: list[str] = []
    error: str | None = None


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
    errors: list[dict] | None = None
    error: str | None = None


# === Helper Functions ===


def get_agent(
    db: AsyncSession,
    config: BacklogAgentConfig | None = None,
) -> Any:
    """Create a BacklogAssistantAgent with database persistence."""
    from ...agents.backlog import BacklogAssistantAgent

    checkpointer = SqlAlchemyCheckpointSaver(db)
    return BacklogAssistantAgent(config=config, checkpointer=checkpointer)


# === API Endpoints ===


@router.post("/decompose", response_model=DecomposeResponse)
async def decompose_epic(
    request: DecomposeRequest,
    project_key: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> DecomposeResponse:
    """
    Decompose an epic into user stories.

    Takes a high-level epic description and breaks it down into
    well-structured user stories with acceptance criteria.

    Returns a thread_id that can be used for subsequent refinement.
    """
    # Build config from request
    config = BacklogAgentConfig(
        USE_MOCKS=True,  # Use mocks by default for safety
        STORY_TEMPLATE=request.story_template,
        DEFAULT_OUTPUT_FORMAT=request.output_format,
        ENABLE_EDGE_CASES=request.enable_edge_cases,
        ENABLE_COMPLEXITY_ESTIMATION=request.enable_complexity_estimation,
    )

    agent = get_agent(db, config)

    result = await agent.decompose(
        epic_description=request.epic_description,
        context=request.context,
        output_format=request.output_format,
        project_key=project_key,
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
    )


@router.post("/chat/{thread_id}", response_model=DecomposeResponse)
async def refine_decomposition(
    thread_id: str,
    request: ChatRequest,
    project_key: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> DecomposeResponse:
    """
    Refine an existing decomposition or start refinement from existing stories.

    This unified endpoint supports:
    1. **Continuation**: Send feedback for stories already in the thread.
    2. **Hydration (Door B)**: Send a list of `stories` in the first message to initialize refinement.

    Examples:
    - "Add more edge cases" (Continuation)
    - "Make these BDD" + [stories] (Hydration)
    """
    agent = get_agent(db)

    result = await agent.chat(
        thread_id=thread_id,
        message=request.message,
        output_format=request.output_format,
        initial_stories=request.stories,
        project_key=project_key,
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
    )


@router.get("/stories/{thread_id}")
async def get_stories(
    thread_id: str,
    output_format: Literal["json", "markdown"] = "json",
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict:
    """
    Get the current decomposition for a thread.

    Returns all stories and the full decomposition result.
    """
    agent = get_agent(db)

    result = await agent.get_stories(thread_id)

    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    # Format output if markdown requested
    if output_format == "markdown" and result.get("result"):
        from ...agents.backlog.schemas import DecompositionResult

        decomp = DecompositionResult.model_validate(result["result"])
        result["formatted_output"] = decomp.to_markdown()

    return result


@router.post("/refine", response_model=DecomposeResponse)
async def refine_existing_stories(
    request: RefineRequest,
    project_key: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> DecomposeResponse:
    """
    Refine existing stories based on user feedback.

    Directly injects existing stories into the agent state and
    processes the feedback message. This is the "Door B" entry point.
    """
    agent = get_agent(db)

    thread_id = request.thread_id or str(uuid.uuid4())

    result = await agent.chat(
        thread_id=thread_id,
        message=request.message,
        output_format=request.output_format,
        initial_stories=request.stories,
        project_key=project_key,
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
    )


@router.post("/export/{thread_id}", response_model=ExportResponse)
async def export_to_jira(
    thread_id: str,
    request: ExportRequest | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
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
    )

    agent = get_agent(db, config)

    result = await agent.export_to_jira(thread_id)

    if result.get("error") and not result.get("export_result"):
        raise HTTPException(status_code=400, detail=result["error"])

    export_result = result.get("export_result", {})

    return ExportResponse(
        thread_id=thread_id,
        status=export_result.get("status", "error"),
        message=export_result.get("message", "Unknown error"),
        issues=export_result.get("issues"),
        errors=export_result.get("errors"),
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
