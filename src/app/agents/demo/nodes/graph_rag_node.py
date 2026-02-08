"""
Graph-RAG Node - Relationship Expansion
========================================
Extends RAG by querying the knowledge graph for related entities.
Finds connections and relationships that pure vector search might miss.

This demonstrates the Graph-RAG feature (V3.0).
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..mocks import MockGraphDB
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class GraphRAGNode:
    """
    Graph-based retrieval node.

    Features:
    - Entity-based relationship discovery
    - Cypher query execution
    - Context enrichment with graph data

    Usage:
        node = GraphRAGNode(config, graph_db)
        new_state = await node(state)
    """

    # Common entity keywords to look for
    ENTITY_KEYWORDS = {
        "legendstack": "Project",
        "fastapi": "System",
        "langgraph": "System",
        "neo4j": "System",
        "pgvector": "System",
        "python": "System",
    }

    def __init__(self, config: DemoAgentConfig, graph_db: MockGraphDB | Any):
        """Initialize with dependencies."""
        self.config = config
        self.graph_db = graph_db

    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Expand context with graph relationships.

        Args:
            state: Current agent state

        Returns:
            Updated state with enriched context
        """
        if not self.config.ENABLE_GRAPH_RAG:
            logger.info("GraphRAGNode: Graph-RAG disabled, skipping")
            return {}

        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("GraphRAGNode: Skipping due to cache hit")
            return {}

        query = state.get("sanitized_input", "").lower()
        current_context = state.get("context", "")

        logger.info("GraphRAGNode: Searching for entity relationships")

        # Find mentioned entities
        found_entities = []
        for keyword, entity_type in self.ENTITY_KEYWORDS.items():
            if keyword in query:
                found_entities.append(keyword)

        if not found_entities:
            logger.info("GraphRAGNode: No known entities found in query")
            return {}

        # Get graph context
        graph_context_parts = []
        for entity in found_entities:
            try:
                results = await self.graph_db.execute_query("MATCH (n {name: $name}) RETURN n", {"name": entity})

                for result in results:
                    node = result.get("node", {})
                    related = result.get("related", [])

                    graph_context_parts.append(f"Entity: {node.get('name')} ({node.get('label')})")

                    for rel in related:
                        graph_context_parts.append(f"  - {rel['relationship']} → {rel['name']} ({rel['label']})")

            except Exception as e:
                logger.error(f"GraphRAGNode: Query failed for {entity} - {e}")

        if graph_context_parts:
            graph_context = "\n\n📊 Knowledge Graph Context:\n" + "\n".join(graph_context_parts)
            enriched_context = current_context + graph_context
            logger.info(f"GraphRAGNode: Added {len(found_entities)} entity relationships")
            return {"context": enriched_context}

        return {}
