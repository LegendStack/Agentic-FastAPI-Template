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
from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .config import BacklogAgentConfig
from .nodes import (
    DecomposeNode,
    ExportNode,
    FormatNode,
    InputNode,
    PrioritizeNode,
    RefineNode,
)
from .schemas import DecompositionResult
from .state import BacklogAgentState

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
    ):
        """
        Initialize the Backlog Assistant Agent.

        Args:
            config: Optional configuration. Defaults to all features enabled with mocks.
            checkpointer: Optional LangGraph checkpointer for state persistence.
        """
        self.config = config or BacklogAgentConfig()
        self.checkpointer = checkpointer

        # Initialize nodes
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
        """Initialize all workflow nodes."""
        self.input_node = InputNode()
        self.decompose_node = DecomposeNode(config=self.config)
        self.refine_node = RefineNode(config=self.config)
        self.format_node = FormatNode(config=self.config)
        self.prioritize_node = PrioritizeNode(config=self.config)
        self.save_node = ExportNode(config=self.config)

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        Flow:
            START → input → [decompose | refine] → format → END
                                                      ↓
                                           (optional) export

        The graph routes based on whether this is a new decomposition
        or a refinement of an existing one.
        """
        workflow = StateGraph(BacklogAgentState)

        # Add nodes
        workflow.add_node("input", self.input_node)
        workflow.add_node("decompose", self.decompose_node)
        workflow.add_node("refine", self.refine_node)
        workflow.add_node("format", self.format_node)
        workflow.add_node("prioritize", self.prioritize_node)
        workflow.add_node("save_to_jira", self.save_node)

        # Define edges
        workflow.add_edge(START, "input")

        # Conditional routing after input
        workflow.add_conditional_edges(
            "input",
            self._route_after_input,
            {
                "decompose": "decompose",
                "refine": "refine",
                "save_to_jira": "save_to_jira",
                "error": END,
            },
        )

        # Decompose and Refine go to Prioritize
        workflow.add_edge("decompose", "prioritize")
        workflow.add_edge("refine", "prioritize")
        
        # Prioritize goes to format
        workflow.add_edge("prioritize", "format")
        workflow.add_edge("save_to_jira", "format")

        # Format goes to end
        workflow.add_edge("format", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _route_after_input(self, state: BacklogAgentState) -> str:
        """Route based on whether this is a new decomposition or refinement."""
        is_save = state.get("is_save_requested")
        is_first = state.get("is_first_message")
        has_stories = bool(state.get("stories"))

        logger.info(f"BacklogAgent: Routing - save_req={is_save}, first={is_first}, has_stories={has_stories}")

        if state.get("error"):
            return "error"

        if is_save:
            return "save_to_jira"

        if is_first or not has_stories:
            return "decompose"

        return "refine"

    async def decompose(
        self,
        epic_description: str,
        context: str | None = None,
        output_format: Literal["json", "markdown", "jira"] = "json",
        thread_id: str | None = None,
        project_key: str | None = None,
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

        return await self.chat(
            thread_id=thread_id,
            message=full_input,
            output_format=output_format,
            project_key=project_key,
        )

    async def chat(
        self,
        thread_id: str,
        message: str,
        output_format: Literal["json", "markdown", "jira"] | None = None,
        initial_stories: list[Any] | None = None,
        project_key: str | None = None,
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
            except Exception:
                pass  # No saved state, will start fresh

        # Build new state
        messages = existing_state.get("messages", [])
        messages.append({"role": "user", "content": message})
        
        logger.info(f"BacklogAssistantAgent: Chat loop starting. is_first={not existing_state.get('stories')}")

        initial_state: BacklogAgentState = {
            "messages": messages,
            "epic_input": existing_state.get("epic_input", ""),
            "parsed_epic": existing_state.get("parsed_epic"),
            "stories": initial_stories or existing_state.get("stories", []),
            "current_result": existing_state.get("current_result"),
            "refinement_feedback": None,
            "is_first_message": not existing_state.get("stories"),
            "is_save_requested": False,
            "output_format": output_format or existing_state.get("output_format", self.config.DEFAULT_OUTPUT_FORMAT),
            "story_template": existing_state.get("story_template", self.config.STORY_TEMPLATE),
            "formatted_output": None,
            "export_result": None,
            "thread_id": thread_id,
            "tenant_id": None,
            "project_key": project_key or existing_state.get("project_key"),
            "error": None,
            "metadata": existing_state.get("metadata", {}),
        }

        if self.checkpointer:
            # Sync with ConversationService for history tracking
            # We do this asynchronously to avoid blocking the main flow if possible,
            # but here we'll await it to ensure consistency.
            if hasattr(self.checkpointer, "db"):
                from ..conversations import ConversationService

                conversation_service = ConversationService(self.checkpointer.db)

                # Ensure conversation exists
                existing_conv = await conversation_service.get_conversation(thread_id)
                if not existing_conv:
                    await conversation_service.create_conversation(
                        thread_id=thread_id,
                        agent_name="backlog_assistant",
                        title=existing_state.get("epic_input", "New Epic")[:50] + "..."
                        if existing_state.get("epic_input")
                        else "New Conversation",
                    )

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

        response = {
            "thread_id": thread_id,
            "response": current_result.model_dump() if current_result else None,
            "formatted_output": final_state.get("formatted_output"),
            "stories": [s.model_dump() if hasattr(s, "model_dump") else s for s in final_state.get("stories", [])],
            "summary": current_result.summary if current_result else None,
            "story_count": len(final_state.get("stories", [])),
            "output_format": final_state.get("output_format"),
            "metadata": {
                "is_refinement": not final_state.get("is_first_message", True),
                "config": {
                    "story_template": self.config.STORY_TEMPLATE,
                    "enabled_features": self.config.get_enabled_features(),
                },
            },
            "usage": final_state.get("usage_metadata"),
        }

        # Add assistant message to conversation
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

            # Update title based on result summary if it's the first message
            if not existing_state.get("stories"):
                summary_title = current_result.summary.split("\n")[0][:50]
                await conversation_service.update_conversation_title(thread_id, summary_title)

        return response

    async def save_to_jira(self, thread_id: str) -> dict[str, Any]:
        """
        Save the current decomposition to JIRA.

        Requires JIRA configuration and ENABLE_JIRA_EXPORT=True.

        Args:
            thread_id: Thread ID with existing decomposition

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
        except Exception as e:
            return {
                "thread_id": thread_id,
                "error": f"Failed to retrieve state: {e}",
                "export_result": None,
            }

        # Run save node
        save_result = await self.save_node(state)
        
        # Update state with Jira info if successful
        if save_result.get("stories") and self.checkpointer:
            new_state = {**state, "stories": save_result["stories"]}
            await self.graph.aupdate_state(config, new_state)
            
            # Post links back to conversation
            if hasattr(self.checkpointer, "db"):
                from ..conversations import ConversationService
                conversation_service = ConversationService(self.checkpointer.db)
                
                issues = save_result.get("export_result", {}).get("issues", [])
                if issues:
                    links_text = "🚀 **JIRA issues saved successfully!**\n\n"
                    for issue in issues:
                        links_text += f"- [{issue['jira_key']}]({issue['url']}) - {issue.get('summary', '')}\n"
                    
                    await conversation_service.add_message(
                        thread_id=thread_id,
                        role="assistant",
                        content=links_text
                    )

        return {
            "thread_id": thread_id,
            "export_result": save_result.get("export_result"),
            "stories": save_result.get("stories", []),
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
                    metadata = conv.metadata_json or {}

            return {
                "thread_id": thread_id,
                "stories": [s.model_dump() if hasattr(s, "model_dump") else s for s in state.get("stories", [])],
                "result": current_result.model_dump() if current_result else None,
                "messages": state.get("messages", []),
                "metadata": metadata,
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
