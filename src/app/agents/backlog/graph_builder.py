"""
Graph Builder
=============
Builds and wires the LangGraph workflow for the Backlog Assistant Agent.

This module extracts graph construction logic from BacklogAssistantAgent,
making it easier to:
- Understand the workflow structure
- Test graph routing logic
- Modify the workflow without touching the agent class

The graph flow is:
    START → input → entity_extractor → intent_classifier → [decompose | refine | help | ...]
                                                           ↓
                                                   (optional nodes)
                                                           ↓
                                                        format → END
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .intents import UserIntent
from .state import BacklogAgentState

if TYPE_CHECKING:
    from .node_factory import NodeInstances

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds the LangGraph workflow for the Backlog Assistant.

    Separates graph construction from the agent orchestration logic,
    making the workflow structure explicit and testable.

    Example:
        factory = NodeFactory(config, jira_service)
        nodes = factory.create_all(help_fn, view_fn, groom_fn)

        builder = GraphBuilder(nodes)
        graph = builder.build(checkpointer)
    """

    def __init__(self, nodes: NodeInstances):
        """
        Initialize the graph builder.

        Args:
            nodes: All instantiated nodes from NodeFactory
        """
        self.nodes = nodes

    def build(self, checkpointer: BaseCheckpointSaver | None = None) -> StateGraph:
        """
        Build and compile the LangGraph workflow.

        Args:
            checkpointer: Optional checkpointer for conversation persistence

        Returns:
            Compiled StateGraph ready for execution
        """
        logger.info("GraphBuilder: Building workflow graph")

        workflow = StateGraph(BacklogAgentState)

        # Add all nodes
        self._add_nodes(workflow)

        # Add edges
        self._add_edges(workflow)

        # Compile with checkpointer
        compiled = workflow.compile(checkpointer=checkpointer)

        logger.info("GraphBuilder: Graph compiled successfully")
        return compiled

    def _add_nodes(self, workflow: StateGraph) -> None:
        """Add all nodes to the workflow."""
        nodes = self.nodes

        # Core processing nodes
        workflow.add_node("input", nodes.input_node)
        workflow.add_node("entity_extractor", nodes.entity_extraction_node)
        workflow.add_node("intent_classifier", nodes.intent_node)

        # Intent-specific nodes
        workflow.add_node("decompose", nodes.decompose_node)
        workflow.add_node("refine", nodes.refine_node)
        workflow.add_node("enhance", nodes.enhance_node)
        workflow.add_node("help", nodes.help_node)
        workflow.add_node("view", nodes.view_node)
        workflow.add_node("groom", nodes.groom_node)

        # Quality and output nodes
        workflow.add_node("critic", nodes.critic_node)
        workflow.add_node("test_gen", nodes.test_gen_node)
        workflow.add_node("format", nodes.format_node)
        workflow.add_node("prioritize", nodes.prioritize_node)
        workflow.add_node("save_to_jira", nodes.export_node)

    def _add_edges(self, workflow: StateGraph) -> None:
        """Add edges between nodes."""
        # Initial flow: START → input → entity_extractor → intent_classifier
        workflow.add_edge(START, "input")
        workflow.add_edge("input", "entity_extractor")
        workflow.add_edge("entity_extractor", "intent_classifier")

        # Conditional routing after intent classification
        workflow.add_conditional_edges(
            "intent_classifier",
            self._route_after_intent,
            {
                "decompose": "decompose",
                "refine": "refine",
                "enhance": "enhance",
                "help": "help",
                "view": "view",
                "groom": "groom",
                "save_to_jira": "save_to_jira",
                "error": END,
            },
        )

        # Decompose and Refine go to Critic
        workflow.add_edge("decompose", "critic")
        workflow.add_edge("refine", "critic")

        # Critic → TestGen → Prioritize (sequenced for now)
        workflow.add_edge("critic", "test_gen")
        workflow.add_edge("test_gen", "prioritize")

        # Prioritize and export go to format
        workflow.add_edge("prioritize", "format")
        workflow.add_edge("save_to_jira", "format")

        # Help, View, Groom, and Enhance go directly to format
        workflow.add_edge("help", "format")
        workflow.add_edge("view", "format")
        workflow.add_edge("groom", "format")
        workflow.add_edge("enhance", "format")

        # Format goes to end
        workflow.add_edge("format", END)

    def _route_after_intent(self, state: BacklogAgentState) -> str:
        """
        Route based on detected intent and state.

        This is the core routing logic that determines which node to execute
        based on the user's intent and the current state.
        """
        is_save = state.get("is_save_requested")
        has_stories = bool(state.get("stories"))
        intent = state.get("detected_intent", UserIntent.DECOMPOSE.value)

        logger.info(f"GraphBuilder: Routing - save_req={is_save}, intent={intent}, has_stories={has_stories}")

        # Error takes precedence
        if state.get("error"):
            return "error"

        # Save request takes precedence
        if is_save:
            return "save_to_jira"

        # Route based on detected intent
        if intent == UserIntent.HELP.value:
            return "help"
        elif intent == UserIntent.VIEW.value:
            return "view"
        elif intent == UserIntent.GROOM.value:
            return "groom" if has_stories else "help"
        elif intent == UserIntent.ENHANCE.value:
            return "enhance" if has_stories else "decompose"
        elif intent == UserIntent.REFINE.value:
            return "refine" if has_stories else "decompose"
        else:
            # Default to decompose for DECOMPOSE or UNKNOWN intents
            return "decompose"

    def get_workflow_diagram(self) -> str:
        """
        Generate a Mermaid diagram of the workflow.

        Useful for documentation and debugging.
        """
        return """
```mermaid
graph TD
    START([START]) --> input
    input --> entity_extractor
    entity_extractor --> intent_classifier
    
    intent_classifier -->|DECOMPOSE| decompose
    intent_classifier -->|REFINE| refine
    intent_classifier -->|ENHANCE| enhance
    intent_classifier -->|HELP| help
    intent_classifier -->|VIEW| view
    intent_classifier -->|GROOM| groom
    intent_classifier -->|SAVE| save_to_jira
    intent_classifier -->|ERROR| END
    
    decompose --> critic
    refine --> critic
    critic --> test_gen
    test_gen --> prioritize
    prioritize --> format
    
    save_to_jira --> format
    help --> format
    view --> format
    groom --> format
    enhance --> format
    
    format --> END([END])
```
"""
