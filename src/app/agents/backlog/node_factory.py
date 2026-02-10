"""
Node Factory
=============
Factory for creating node instances with proper dependency injection.

This module centralizes node instantiation, making it easy to:
- Inject services (JiraService, etc.) into nodes that need them
- Swap implementations for testing
- Configure nodes consistently

Example Usage:
    jira_service = JiraService(config)
    factory = NodeFactory(config=agent_config, jira_service=jira_service)

    nodes = factory.create_all()
    # nodes.input_node, nodes.decompose_node, nodes.export_node, etc.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..azure_openai import get_llm_service

if TYPE_CHECKING:
    from ...services.jira_service import JiraService
    from .config import BacklogAgentConfig

logger = logging.getLogger(__name__)


@dataclass
class NodeInstances:
    """Container for all instantiated nodes."""

    # Core nodes
    input_node: Any
    entity_extraction_node: Any
    intent_node: Any
    decompose_node: Any
    refine_node: Any
    enhance_node: Any
    critic_node: Any
    test_gen_node: Any
    format_node: Any
    prioritize_node: Any
    export_node: Any

    # Inline node functions (help, view, groom)
    help_node: Callable
    view_node: Callable
    groom_node: Callable


class NodeFactory:
    """
    Factory for creating agent nodes with proper dependency injection.

    Centralizes node creation to ensure:
    - Consistent configuration across all nodes
    - Proper service injection (JiraService, etc.)
    - Easy testing with mock services
    """

    def __init__(
        self,
        config: BacklogAgentConfig,
        jira_service: JiraService | None = None,
    ):
        """
        Initialize the node factory.

        Args:
            config: Agent configuration
            jira_service: Optional JiraService for nodes that need Jira access
        """
        self.config = config
        self.jira_service = jira_service

    def create_all(
        self,
        help_node_fn: Callable,
        view_node_fn: Callable,
        groom_node_fn: Callable,
    ) -> NodeInstances:
        """
        Create all node instances.

        Args:
            help_node_fn: The help node function (inline)
            view_node_fn: The view node function (inline)
            groom_node_fn: The groom node function (inline)

        Returns:
            NodeInstances containing all nodes
        """
        from .nodes import (
            CriticNode,
            DecomposeNode,
            EntityExtractionNode,
            ExportNode,
            FormatNode,
            InputNode,
            IntentNode,
            PrioritizeNode,
            RefineNode,
            StoryEnhanceNode,
            TestGenNode,
        )

        logger.info("NodeFactory: Creating all node instances")

        # Create nodes with proper dependency injection
        return NodeInstances(
            # Input processing
            input_node=InputNode(),
            entity_extraction_node=self._create_entity_extraction_node(EntityExtractionNode),
            intent_node=IntentNode(llm=get_llm_service()),
            # Core processing
            decompose_node=DecomposeNode(
                config=self.config,
                llm_service=get_llm_service(),
                jira_service=self.jira_service,
            ),
            refine_node=RefineNode(config=self.config),
            enhance_node=StoryEnhanceNode(config=self.config),
            # Quality and formatting
            critic_node=CriticNode(config=self.config),
            test_gen_node=TestGenNode(config=self.config),
            format_node=FormatNode(config=self.config),
            prioritize_node=PrioritizeNode(config=self.config),
            # Export with injected JiraService
            export_node=self._create_export_node(ExportNode),
            # Inline functions
            help_node=help_node_fn,
            view_node=view_node_fn,
            groom_node=groom_node_fn,
        )

    def _create_entity_extraction_node(self, cls):
        """
        Create EntityExtractionNode with injected JiraService.

        This removes the circular HTTP dependency by injecting the service directly.
        """
        return cls(jira_service=self.jira_service)

    def _create_export_node(self, cls):
        """
        Create ExportNode with injected JiraService.

        This centralizes Jira operations through the service.
        """
        return cls(config=self.config, jira_service=self.jira_service)
