"""
Backlog Assistant Agent
=======================
Main agent class that orchestrates the story decomposition workflow.

This agent uses LangGraph to manage a conversational workflow that:
1. Parses epic descriptions
2. Decomposes into user stories
3. Refines based on user feedback
4. Formats output (JSON/Markdown/JIRA)
5. Optionally exports to JIRA

REFACTORED: Delegates node creation to NodeFactory and graph building to GraphBuilder
for cleaner architecture and dependency injection.

Example Usage:
    # Basic decomposition
    agent = BacklogAssistantAgent()
    result = await agent.decompose(
        "We need to add SSO login support for enterprise customers"
    )

    # With conversation for refinement
    result = await agent.chat(
        thread_id="abc123",
        message="Add more edge cases to the authentication stories"
    )

    # Export to JIRA
    result = await agent.export_to_jira(thread_id="abc123")
"""

import logging
import uuid
from typing import TYPE_CHECKING, Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver

from ...core.config import settings
from ..conversations import ConversationService
from .config import BacklogAgentConfig
from .graph_builder import GraphBuilder
from .intents import UserIntent
from .node_factory import NodeFactory
from .schemas import DecompositionResult
from .state import BacklogAgentState

if TYPE_CHECKING:
    from ...services.jira_service import JiraService

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class BacklogAssistantAgent:
    """
    Backlog Assistant Agent - Story Decomposition with Conversational Refinement.

    A state-of-the-art agent for breaking down epics into user stories.
    Features modular LangGraph workflow, structured output, and JIRA integration.

    Attributes:
        config: Agent configuration with feature toggles
        checkpointer: Optional persistence for conversation state

    Example:
        # Quick decomposition
        agent = BacklogAssistantAgent()
        result = await agent.decompose("Add user authentication")

        # Custom configuration
        config = BacklogAgentConfig(
            STORY_TEMPLATE="bdd",
            ENABLE_EDGE_CASES=True,
            MAX_STORIES_PER_EPIC=8
        )
        agent = BacklogAssistantAgent(config=config)

        # With conversation persistence
        from ..persistence import SqlAlchemyCheckpointSaver
        checkpointer = SqlAlchemyCheckpointSaver(db)
        agent = BacklogAssistantAgent(checkpointer=checkpointer)
    """

    def __init__(
        self,
        config: BacklogAgentConfig | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        jira_service: "JiraService | None" = None,
    ):
        """
        Initialize the Backlog Assistant Agent.

        Args:
            config: Optional configuration. Defaults to all features enabled with mocks.
            checkpointer: Optional LangGraph checkpointer for state persistence.
            jira_service: Optional JiraService for dependency injection.
                          If provided, nodes that need Jira access will use this service.
        """
        self.config = config or BacklogAgentConfig()
        self.checkpointer = checkpointer
        self._jira_service = jira_service

        # Initialize nodes (with injected JiraService if provided)
        self._init_nodes()

        # Build the graph
        self.graph = self._build_graph()

        logger.info(f"BacklogAssistantAgent initialized with features: {self.config.get_enabled_features()}")

    async def initialize(self) -> None:
        """
        Ensure all required infrastructure is ready.
        Call this before using the agent for the first time.
        """
        logger.info("BacklogAssistantAgent: Initializing infrastructure...")

        # 1. Ensure RAG index exists if using Azure Search
        from ...core.config import RAGBackend, settings
        from ..vector_stores import VectorStoreFactory

        if settings.RAG_BACKEND == RAGBackend.AZURE_SEARCH:
            try:
                # We don't need a DB session yet just to check/create the index
                store = VectorStoreFactory.get_store(None)
                if hasattr(store, "create_index_if_not_exists"):
                    await store.create_index_if_not_exists()
            except Exception as e:
                logger.error(f"BacklogAssistantAgent: Failed to initialize Azure Search index - {e}")
                # We don't raise here to allow the agent to start in degraded mode if needed
                # (e.g. if the user just wants to decompose without indexing)

        logger.info("BacklogAssistantAgent: Infrastructure initialization complete.")

    def _init_nodes(self) -> None:
        """
        Initialize all workflow nodes using NodeFactory.

        Delegates node creation to NodeFactory for proper dependency injection.
        """
        factory = NodeFactory(
            config=self.config,
            jira_service=self._jira_service,
        )

        # Create all nodes via factory
        self._nodes = factory.create_all(
            help_node_fn=self._help_node,
            view_node_fn=self._view_node,
            groom_node_fn=self._groom_node,
        )

        logger.info("BacklogAssistantAgent: Nodes initialized via NodeFactory")

    def _build_graph(self):
        """
        Build the LangGraph workflow using GraphBuilder.

        Delegates graph construction to GraphBuilder for cleaner separation.

        Flow:
            START → input → entity_extractor → intent_classifier → [decompose | refine | help | groom]
                                                                   ↓
                                                        (optional) export
        """
        builder = GraphBuilder(self._nodes)
        graph = builder.build(checkpointer=self.checkpointer)

        logger.info("BacklogAssistantAgent: Graph built via GraphBuilder")
        return graph

    def _route_after_intent(self, state: BacklogAgentState) -> str:
        """Route based on detected intent and state."""
        is_save = state.get("is_save_requested")
        has_stories = bool(state.get("stories"))
        intent = state.get("detected_intent", UserIntent.DECOMPOSE.value)

        logger.info(f"BacklogAgent: Routing - save_req={is_save}, intent={intent}, has_stories={has_stories}")

        if state.get("error"):
            return "error"

        if is_save:
            return "save_to_jira"

        # Route based on detected intent
        if intent == UserIntent.HELP.value:
            return "help"
        elif intent == UserIntent.VIEW.value:
            return "view"
        elif intent == UserIntent.GROOM.value:
            if has_stories:
                return "groom"
            else:
                # Can't groom without stories, fallback to help
                return "help"
        elif intent == UserIntent.ENHANCE.value:
            if has_stories:
                return "enhance"
            else:
                # Can't enhance without stories, fallback to decompose
                return "decompose"
        elif intent == UserIntent.REFINE.value:
            if has_stories:
                return "refine"
            else:
                # Can't refine without stories, fallback to decompose
                return "decompose"
        elif intent in [
            UserIntent.DECOMPOSE.value,
            UserIntent.DECOMPOSE_TO_EPICS.value,
            UserIntent.DECOMPOSE_TO_STORIES.value,
            UserIntent.DECOMPOSE_TO_TASKS.value,
            UserIntent.DECOMPOSE_TO_SUBTASKS.value,
        ]:
            return "decompose"
        else:
            # Default to decompose for DECOMPOSE or UNKNOWN intents
            return "decompose"

    async def _help_node(self, state: BacklogAgentState) -> dict:
        """Generate a help response explaining agent capabilities."""
        project_key = state.get("project_key", "your project")
        has_stories = bool(state.get("stories"))

        capabilities = [
            "📋 **Multi-Level Decomposition**: I can break down requirements into **Epics**, **Stories**, **Tasks**, or **Sub-tasks**.",
            "📝 **Targeted Breakdown**: Ask me to 'decompose into epics' or 'breakdown into tasks' for specific levels.",
            "✨ **Refine Stories**: Ask me to add more details, edge cases, or improve any story's acceptance criteria.",
            "🔍 **Analyze Backlog**: Request a grooming analysis to find duplicates, dependencies, or quality gaps.",
            "💾 **Export to Jira**: Save your refined stories directly to Jira with proper linking.",
        ]

        context_hint = ""
        if has_stories:
            story_count = len(state.get("stories", []))
            context_hint = f"\n\n📋 **Current Session**: You have {story_count} stories in your backlog. Try asking me to refine them or analyze for duplicates!"

        help_text = f"""# 👋 Hello! I'm your Backlog Assistant

I help agile teams create high-quality user stories from epic descriptions.

## What I Can Do:

{chr(10).join(capabilities)}
{context_hint}

## Quick Start:
Just describe your epic or feature, and I'll create a detailed breakdown for you!
"""

        return {"help_response": help_text}

    async def _view_node(self, state: BacklogAgentState) -> dict:
        """Hydrate and format context for specific Jira entities without decomposing."""
        enriched_context = state.get("enriched_context")
        entities = state.get("extracted_entities", [])

        if not enriched_context or not entities:
            return {
                "view_response": "I couldn't find any Jira entities in your message to identify. Please provide a key like 'PROJ-123'."
            }

        # Build a nice display from enriched_context (which already has hydrated info)
        display_text = f"# 🔍 Entity Identity\n\nI've retrieved details for {len(entities)} referenced item(s):\n\n{enriched_context}"

        return {"view_response": display_text}

    async def _groom_node(self, state: BacklogAgentState) -> dict:
        """
        Analyze backlog for quality issues.

        This method delegates to the GroomNode class for comprehensive analysis
        including duplicate detection, dependency mapping, and quality checks.
        """
        # Import here to avoid circular imports
        from .nodes.groom_node import GroomNode

        groom = GroomNode(config=self.config)
        return await groom(state)

    async def decompose(
        self,
        epic_description: str,
        context: str | None = None,
        output_format: Literal["json", "markdown", "jira"] = "json",
        thread_id: str | None = None,
        project_key: str | None = None,
        parent_epic_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Decompose an epic into user stories.

        This is a convenience method for one-shot decomposition.

        Args:
            epic_description: The epic or feature to decompose
            context: Optional additional context (tech stack, constraints)
            output_format: Desired output format
            thread_id: Optional thread ID for persistence

        Returns:
            Dictionary with decomposition result, formatted output, and metadata
        """
        thread_id = thread_id or str(uuid.uuid4())

        # Build full input with context if provided
        full_input = epic_description
        if context:
            full_input += f"\n\nContext: {context}"

        # Quick intent pre-check: Handle obvious non-decompose intents BEFORE duplicate detection
        # This prevents help queries from being matched to cached decompositions
        lower_input = epic_description.lower().strip()
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
        ]

        # View/Identity patterns - user wants to see details, not decompose
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

        # If this looks like a help or view request, go directly to chat (which will route correctly)
        is_help = any(pattern in lower_input for pattern in help_patterns) and len(epic_description) < 100
        is_view = any(pattern in lower_input for pattern in view_patterns) and len(epic_description) < 100

        if is_help or is_view:
            intent_type = "help" if is_help else "view"
            logger.info(f"BacklogAgent.decompose: Detected {intent_type} intent, bypassing duplicate check")
            return await self.chat(
                thread_id=thread_id,
                message=full_input,
                output_format=output_format,
                project_key=project_key,
                parent_epic_id=parent_epic_id,
                user_id=user_id,
            )

        # Check for duplicates if mocks disabled (only for actual decomposition requests)
        if not self.config.USE_MOCKS:
            dup_thread_id = await self._check_duplicate_epic(full_input)
            if dup_thread_id:
                logger.info(f"Retrieved existing decomposition for thread {dup_thread_id}")
                result = await self.get_stories(dup_thread_id)
                if result.get("stories"):
                    current_result = result.get("result", {})
                    return {
                        "thread_id": dup_thread_id,
                        "response": current_result,
                        "formatted_output": None,
                        "stories": result.get("stories", []),
                        "summary": current_result.get("summary")
                        if isinstance(current_result, dict)
                        else getattr(current_result, "summary", None),
                        "story_count": len(result.get("stories", [])),
                        "output_format": output_format,
                        "metadata": {**result.get("metadata", {}), "is_duplicate": True},
                        "usage": {},
                        "target_level": "story",
                        "target_issue_type": "Story",
                    }

        return await self.chat(
            thread_id=thread_id,
            message=full_input,
            output_format=output_format,
            project_key=project_key,
            parent_epic_id=parent_epic_id,
            user_id=user_id,
        )

    async def _check_duplicate_epic(self, epic_description: str) -> str | None:
        """
        Check if an epic with similar description already exists.
        Returns the thread_id of the existing epic if found.
        """
        if not self.checkpointer:
            return None

        try:
            from ..azure_openai import get_llm_service
            from ..vector_stores import VectorStoreFactory

            # We initialize store without DB session as we only read
            store = VectorStoreFactory.get_store(None)
            llm_service = get_llm_service()

            # Use only first 1000 chars for embedding to save tokens/time
            query_vector = await llm_service.get_embeddings(epic_description[:1000])

            # Search for epics in the archive
            # Note: We filter by source_id="epic_archive" which is set by DecomposeNode._archive_epic
            results = await store.similarity_search(query_vector, k=1, filters={"source_id": "epic_archive"})

            if results:
                match = results[0]
                score = match.get("score", 0)
                # High threshold for semantic clone (0.92 is very high)
                if score > 0.92:
                    meta = match.get("metadata", {})
                    thread_id = meta.get("thread_id")
                    if thread_id:
                        logger.info(
                            f"BacklogAssistantAgent: Found duplicate epic (score: {score:.4f}) -> thread {thread_id}"
                        )
                        return thread_id

            return None
        except Exception as e:
            logger.warning(f"BacklogAssistantAgent: Duplicate epic check failed - {e}")
            return None

    async def _generate_smart_title(self, message: str) -> str:
        """Generate a concise 3-5 word title from the user message."""
        try:
            from ..azure_openai import get_llm_service

            llm = get_llm_service()

            prompt = f"""You are a JIRA expert. Generate a concise, professional title (3-5 words) for a conversation based on this user message.
            
            User Message: {message}
            
            Title rules:
            1. Title-cased
            2. 3-5 words only
            3. No quotes, no prefix like "Title:", no period at the end
            4. Focus on the core business feature or project being described.
            5. If the message is a short greeting or help request, make it descriptive (e.g., "General Backlog Assistance" or "System Capability Inquiry").
            
            Title:"""

            response = await llm.chat([{"role": "user", "content": prompt}])
            title = response.content.strip().strip('"').strip("'")
            # Fallback if LLM gives something too long or empty
            if not title or len(title.split()) > 7:
                return message[:50].split("\n")[0] + "..."
            return title
        except Exception as e:
            logger.warning(f"BacklogAgent: Failed to generate smart title - {e}")
            return message[:50].split("\n")[0] + "..."

    async def chat(
        self,
        thread_id: str,
        message: str,
        output_format: Literal["json", "markdown", "jira"] | None = None,
        initial_stories: list[Any] | None = None,
        project_key: str | None = None,
        parent_epic_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a chat message for decomposition or refinement.

        First message creates a decomposition, subsequent messages refine it.

        Args:
            thread_id: Conversation thread identifier
            message: User's message (epic description or refinement feedback)
            output_format: Optional output format override

        Returns:
            Dictionary with:
                - thread_id: The conversation thread ID
                - response: The decomposition result
                - formatted_output: Output in requested format
                - stories: List of user stories
                - metadata: Additional information
        """
        logger.info(f"BacklogAssistantAgent: Processing message for thread {thread_id}")

        # Prepare initial state
        config = {"configurable": {"thread_id": thread_id}}

        # Get existing state if any
        existing_state = {}

        if self.checkpointer:
            try:
                saved_state = await self.graph.aget_state(config)
                if saved_state and saved_state.values:
                    existing_state = saved_state.values

                    # Lock Check: Prevent edits if already exported to Jira
                    if existing_state.get("is_locked"):
                        logger.warning(f"BacklogAgent: Rejected chat for locked thread {thread_id}")
                        return {
                            "thread_id": thread_id,
                            "error": "CONVERSATION_LOCKED: This decomposition has been successfully saved to JIRA. To maintain data integrity, further refinements are disabled.",
                            "response": existing_state.get("current_result"),
                            "stories": existing_state.get("stories", []),
                            "metadata": existing_state.get("metadata", {}),
                        }
            except Exception:
                pass  # No saved state, will start fresh

        # Build new state
        messages = existing_state.get("messages", [])
        messages.append({"role": "user", "content": message})

        is_first = not existing_state.get("stories")
        logger.info(f"BacklogAssistantAgent: Chat loop starting. is_first={is_first}")

        initial_state: BacklogAgentState = {
            "messages": messages,
            "epic_input": existing_state.get("epic_input", ""),
            "parsed_epic": existing_state.get("parsed_epic"),
            "stories": initial_stories or existing_state.get("stories", []),
            "current_result": existing_state.get("current_result"),
            "refinement_feedback": None,
            "is_first_message": is_first,
            "is_save_requested": False,
            "output_format": output_format or existing_state.get("output_format", self.config.DEFAULT_OUTPUT_FORMAT),
            "story_template": existing_state.get("story_template", self.config.STORY_TEMPLATE),
            "formatted_output": None,
            "export_result": None,
            "thread_id": thread_id,
            "tenant_id": None,
            "project_key": project_key or existing_state.get("project_key"),
            "parent_epic_id": parent_epic_id or existing_state.get("parent_epic_id"),
            "user_id": user_id or existing_state.get("user_id"),
            "error": None,
            "metadata": existing_state.get("metadata", {}),
            # Transient fields - RESET at start of each turn to prevent state leakage
            "summary": None,
            "help_response": None,
            "view_response": None,
            "grooming_report": None,
            "detected_intent": None,
            "refinement_feedback": None,
        }

        if self.checkpointer:
            # Sync with ConversationService for history tracking
            if hasattr(self.checkpointer, "db"):
                from ..conversations import ConversationService

                conversation_service = ConversationService(self.checkpointer.db)

                # Ensure conversation exists
                existing_conv = await conversation_service.get_conversation(thread_id)
                if not existing_conv:
                    # Generate smart title instead of simple truncation
                    title = await self._generate_smart_title(message)
                    await conversation_service.create_conversation(
                        thread_id=thread_id,
                        agent_name="backlog_assistant",
                        title=title,
                        user_id=int(user_id) if user_id and user_id.isdigit() else None,
                    )
                elif is_first:
                    # If this is effectively a first message (even if thread existed)
                    title = await self._generate_smart_title(message)
                    await conversation_service.update_conversation(thread_id, title=title)

                # Store project_key in metadata if provided
                if project_key:
                    await conversation_service.update_metadata(thread_id, {"project_key": project_key})

                # Add user message
                await conversation_service.add_message(thread_id=thread_id, role="user", content=message)

        async for event in self.graph.astream(initial_state, config=config, stream_mode="values"):
            final_state = event

        if not final_state:
            return {
                "thread_id": thread_id,
                "error": "No result from agent",
                "response": None,
            }

        # Check for errors
        if final_state.get("error"):
            return {
                "thread_id": thread_id,
                "error": final_state["error"],
                "response": None,
            }

        # Build response
        current_result = final_state.get("current_result")
        if isinstance(current_result, dict):
            current_result = DecompositionResult.model_validate(current_result)

        # Update title if decomposition result has a smart title (Phase 6 Polish)
        if current_result and hasattr(current_result, "conversation_title") and current_result.conversation_title:
            if hasattr(self.checkpointer, "db"):
                from ..conversations import ConversationService
                conversation_service = ConversationService(self.checkpointer.db)
                # Only update if current title is still generic or very short
                existing_conv = await conversation_service.get_conversation(thread_id)
                if existing_conv:
                    current_title = existing_conv.title or ""
                    # If common placeholder or just a truncated version of a short greeting
                    is_generic = current_title in ["New Conversation", "New Chat", "Conversation"]
                    is_short = len(current_title) < 10
                    if is_generic or is_short:
                        await conversation_service.update_conversation(thread_id, title=current_result.conversation_title)

        response = {
            "thread_id": thread_id,
            "response": current_result.model_dump() if current_result else None,
            "formatted_output": final_state.get("formatted_output"),
            "stories": [s.model_dump() if hasattr(s, "model_dump") else s for s in final_state.get("stories", [])],
            "summary": final_state.get("summary") or (current_result.summary if current_result else None),
            "story_count": len(final_state.get("stories", [])),
            "output_format": final_state.get("output_format"),
            "is_locked": final_state.get("is_locked", False),
            "metadata": {
                "is_refinement": not final_state.get("is_first_message", True),
                "config": {
                    "story_template": self.config.STORY_TEMPLATE,
                    "enabled_features": self.config.get_enabled_features(),
                },
            },
            "usage": final_state.get("usage_metadata"),
            "target_level": final_state.get("target_level", "story"),
            "target_issue_type": final_state.get("target_issue_type", "Story"),
        }

        if current_result and self.checkpointer and hasattr(self.checkpointer, "db"):
            from ..conversations import ConversationService

            conversation_service = ConversationService(self.checkpointer.db)

            # Extract token counts
            usage = final_state.get("usage_metadata") or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            # Use content from FormatNode if available (has rich Jira links)
            assistant_messages = [m for m in final_state.get("messages", []) if m.get("role") == "assistant"]
            assistant_content = assistant_messages[-1].get("content") if assistant_messages else current_result.summary

            await conversation_service.add_message(
                thread_id=thread_id,
                role="assistant",
                content=assistant_content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )



        # Audit Logging for Refinement (Phase 57)
        try:
            # Only log if it was a refinement (not first message) and we have a user_id
            if not final_state.get("is_first_message", True) and (user_id or existing_state.get("user_id")):
                from ...core.db.database import AsyncSessionLocal
                from ...services.audit_service import AuditService

                # Resolve user_id if not passed directly
                effective_user_id = user_id or existing_state.get("user_id")

                details = {
                    "message_summary": message[:100] + "..." if len(message) > 100 else message,
                    "story_count": len(final_state.get("stories", [])),
                    "project_key": project_key or final_state.get("project_key"),
                }

                async with AsyncSessionLocal() as db:
                    audit = AuditService(db)
                    await audit.log_event(
                        action="REFINEMENT",
                        resource_type="BACKLOG",
                        resource_id=thread_id,  # Use thread_id as resource for backlog refinement
                        details=details,
                        user_id=effective_user_id,
                        thread_id=thread_id,
                    )
        except Exception as e:
            logger.warning(f"BacklogAgent: Failed to log refinement audit - {e}")

        return response

    async def save_to_jira(self, thread_id: str, user_id: str | None = None) -> dict[str, Any]:
        """
        Save the current decomposition to JIRA.

        Requires JIRA configuration and ENABLE_JIRA_EXPORT=True.

        Args:
            thread_id: Thread ID with existing decomposition
            user_id: ID of the user triggering the export (for audit logging)

        Returns:
            Save result with created issue keys
        """
        logger.info(f"BacklogAssistantAgent: Saving to JIRA for thread {thread_id}")

        if not self.config.ENABLE_JIRA_EXPORT:
            return {
                "thread_id": thread_id,
                "error": "JIRA integration is not enabled. Set ENABLE_JIRA_EXPORT=True in config.",
                "export_result": None,
            }

        # Get current state
        config = {"configurable": {"thread_id": thread_id}}

        if not self.checkpointer:
            return {
                "thread_id": thread_id,
                "error": "No checkpointer configured. Cannot retrieve decomposition state.",
                "export_result": None,
            }

        try:
            saved_state = await self.graph.aget_state(config)
            if not saved_state or not saved_state.values:
                return {
                    "thread_id": thread_id,
                    "error": "No decomposition found for this thread.",
                    "export_result": None,
                }

            state = saved_state.values
            state = saved_state.values
        except Exception as e:
            return {
                "thread_id": thread_id,
                "error": f"Failed to retrieve state: {e}",
                "export_result": None,
            }

        # Inject user_id into state for Audit Logging
        if user_id:
            state["user_id"] = user_id

        # Run save node
        save_result = await self._nodes.export_node(state)

        if save_result.get("stories") and self.checkpointer:
            # Prepare updates
            new_stories = save_result["stories"]
            update_dict = {
                "stories": new_stories,
                "is_locked": True,  # Phase 8 Fix: Persist lock status
            }

            # Post links back to conversation and update state with message
            if hasattr(self.checkpointer, "db"):
                conversation_service = ConversationService(self.checkpointer.db)

                # save_result IS the dictionary returned by ExportNode.__call__
                # which contains "export_result"
                export_result = save_result.get("export_result", {})
                issues = export_result.get("issues", [])

                if issues:
                    # Separate Epic from stories
                    epic_key = export_result.get("epic_key")
                    epic_issue = next((i for i in issues if i.get("internal_id") == "EPIC"), None)
                    # Also check issues list for the epic_key in case internal_id isn't "EPIC"
                    if not epic_issue and epic_key:
                        epic_issue = next((i for i in issues if i.get("jira_key") == epic_key), None)

                    error_issues = export_result.get("errors", [])

                    # Filter out the Epic itself from the stories list for the summary
                    story_issues = [i for i in issues if i.get("internal_id") != "EPIC" and i.get("jira_key") != epic_key]

                    # Dynamic Phrasing (Phase 51 Fix)
                    target_issue_type = state.get("target_issue_type") or "Story"
                    if target_issue_type == "Epic":
                        items_label = "Epics"
                    elif target_issue_type == "Task":
                        items_label = "Tasks"
                    elif target_issue_type == "Sub-task":
                        items_label = "Sub-tasks"
                    else:
                        items_label = "User Stories"

                    if not story_issues and error_issues:
                         links_text = "⚠️ **JIRA export completed with errors.**\n\n"
                    else:
                         links_text = "🚀 **JIRA issues saved successfully!**\n\n"

                    if epic_key:
                        if epic_issue:
                            links_text += "**Epic Created/Linked:**\n"
                            links_text += f"- [{epic_issue['jira_key']}]({epic_issue['url']}) - {epic_issue.get('summary', 'Parent Epic')}\n\n"
                        else:
                            base_url = settings.JIRA_URL or "https://jira.atlassian.net"
                            summary = ""
                            parsed_epic = state.get("parsed_epic")
                            if parsed_epic:
                                # parsed_epic might be a dict or a model
                                summary = (
                                    parsed_epic.title if hasattr(parsed_epic, "title") else parsed_epic.get("title", "")
                                )

                            links_text += "**Linked to Parent Epic:**\n"
                            links_text += (
                                f"- [{epic_key}]({base_url}/browse/{epic_key}){f' - {summary}' if summary else ''}\n\n"
                            )

                        links_text += f"**{items_label} Decomposed:**\n"
                    else:
                        links_text += f"**{items_label} Created:**\n"

                    for issue in story_issues:
                        links_text += f"- [{issue['jira_key']}]({issue['url']}) - {issue.get('summary', '')}\n"

                    if error_issues:
                        links_text += f"\n❌ **Errors Encountered ({len(error_issues)}):**\n"
                        for error in error_issues:
                            item_id = error.get("story_id", "Unknown")
                            error_msg = error.get("error", "Unknown error")
                            links_text += f"- **{item_id}**: {error_msg}\n"

                    try:
                        await conversation_service.add_message(
                            thread_id=thread_id, role="assistant", content=links_text
                        )
                        # Add to graph state messages as well so it appears in get_stories
                        messages = state.get("messages", [])
                        new_message = {"role": "assistant", "content": links_text}
                        update_dict["messages"] = messages + [new_message]

                    except Exception:
                        logger.exception(
                            f"BacklogAssistantAgent: Failed to post Jira links message to thread {thread_id}"
                        )

        # Update state ONCE with stories and potentially new message
        is_locked = save_result.get("is_locked", False)
        new_state = {**state, **update_dict, "is_locked": is_locked}
        await self.graph.aupdate_state(config, new_state)

        return {
            "thread_id": thread_id,
            "export_result": save_result.get("export_result"),
            "stories": save_result.get("stories", []),
            "is_locked": save_result.get("is_locked", False),
            "error": save_result.get("error"),
        }

    async def get_stories(self, thread_id: str) -> dict[str, Any]:
        """
        Get the current decomposition for a thread.

        Args:
            thread_id: Thread ID to retrieve

        Returns:
            Current decomposition result or error
        """
        if not self.checkpointer:
            return {
                "thread_id": thread_id,
                "error": "No checkpointer configured",
                "stories": [],
            }

        config = {"configurable": {"thread_id": thread_id}}

        try:
            saved_state = await self.graph.aget_state(config)
            if not saved_state or not saved_state.values:
                return {
                    "thread_id": thread_id,
                    "error": "No decomposition found for this thread",
                    "stories": [],
                }

            state = saved_state.values
            current_result = state.get("current_result")

            if isinstance(current_result, dict):
                current_result = DecompositionResult.model_validate(current_result)

            # Get metadata from ConversationService if available
            metadata = {}
            if hasattr(self.checkpointer, "db"):
                from ..conversations import ConversationService

                conversation_service = ConversationService(self.checkpointer.db)
                conv = await conversation_service.get_conversation(thread_id)
                if conv:
                    if conv.status == "archived":
                        return {
                            "thread_id": thread_id,
                            "error": "Conversation is archived",
                            "stories": [],
                        }
                    metadata = conv.metadata_json or {}

            return {
                "thread_id": thread_id,
                "stories": [s.model_dump() if hasattr(s, "model_dump") else s for s in state.get("stories", [])],
                "result": current_result.model_dump() if current_result else None,
                "messages": state.get("messages", []),
                "is_locked": state.get("is_locked", False),
                "metadata": metadata,
                "target_level": state.get("target_level", "story"),
                "target_issue_type": state.get("target_issue_type", "Story"),
            }

        except Exception as e:
            return {
                "thread_id": thread_id,
                "error": f"Failed to retrieve stories: {e}",
                "stories": [],
            }

    async def get_stories_at_version(self, thread_id: str, checkpoint_id: str) -> dict[str, Any]:
        """
        Get the decomposition result at a specific version (checkpoint).

        Args:
            thread_id: Thread ID to retrieve
            checkpoint_id: Specific checkpoint ID (version)

        Returns:
            Decomposition result at that version or error
        """
        if not self.checkpointer:
            return {
                "thread_id": thread_id,
                "error": "No checkpointer configured",
                "stories": [],
            }

        config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}

        try:
            saved_state = await self.graph.aget_state(config)
            if not saved_state or not saved_state.values:
                return {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "error": "No decomposition found for this specific version",
                    "stories": [],
                }

            state = saved_state.values
            current_result = state.get("current_result")

            if isinstance(current_result, dict):
                current_result = DecompositionResult.model_validate(current_result)

            return {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "stories": [s.model_dump() if hasattr(s, "model_dump") else s for s in state.get("stories", [])],
                "result": current_result.model_dump() if current_result else None,
                "summary": current_result.summary if current_result else None,
                "messages": state.get("messages", []),
                "is_locked": state.get("is_locked", False),
                "target_level": state.get("target_level", "story"),
                "target_issue_type": state.get("target_issue_type", "Story"),
            }

        except Exception as e:
            return {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "error": f"Failed to retrieve version {checkpoint_id}: {e}",
                "stories": [],
            }

    def get_config_summary(self) -> dict[str, Any]:
        """Get a summary of the current agent configuration."""
        return {
            "story_template": self.config.STORY_TEMPLATE,
            "story_template_description": self.config.get_story_template_description(),
            "output_format": self.config.DEFAULT_OUTPUT_FORMAT,
            "enabled_features": self.config.get_enabled_features(),
            "max_stories": self.config.MAX_STORIES_PER_EPIC,
            "jira_export_enabled": self.config.ENABLE_JIRA_EXPORT,
            "using_mocks": self.config.USE_MOCKS,
        }


# === CLI Demo Runner ===
if __name__ == "__main__":
    import asyncio

    async def demo():
        """Run a quick demo of the Backlog Assistant Agent."""
        print("=" * 60)
        print("Backlog Assistant Agent Demo")
        print("=" * 60)

        # Create agent with default config (mocks enabled)
        agent = BacklogAssistantAgent()

        print("\n📋 Agent Configuration:")
        print(agent.get_config_summary())

        # Test decomposition
        epic = """
        Add Single Sign-On (SSO) login support for enterprise customers.
        We need to support both SAML 2.0 and OIDC protocols.
        
        Context: We use Azure AD as our primary IdP. The existing login 
        system uses JWT tokens. We need to maintain backward compatibility.
        """

        print("\n🎯 Decomposing Epic:")
        print(epic.strip())
        print("\n" + "-" * 40)

        result = await agent.decompose(epic, output_format="json")

        if result.get("error"):
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Generated {result['story_count']} stories")
            print(f"\n📝 Summary: {result['summary']}")
            print("\n📖 Stories:")
            for story in result.get("stories", []):
                print(f"  - [{story.get('id')}] {story.get('title')}")
                print(f"    Complexity: {story.get('estimated_complexity', 'N/A')}")

    asyncio.run(demo())
