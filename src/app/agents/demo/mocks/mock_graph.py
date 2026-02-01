"""
Mock Graph Database
====================
An in-memory graph database for testing and demo purposes.
Simulates Neo4j operations for entity storage and relationship queries.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MockNode:
    """A graph node with label, properties, and relationships."""
    name: str  # Primary identifier
    label: str  # Node type (Person, Project, System, etc.)
    properties: dict[str, Any] = field(default_factory=dict)
    tenant_id: str | None = None


@dataclass
class MockRelationship:
    """A relationship between two nodes."""
    source: str  # Source node name
    target: str  # Target node name
    type: str  # Relationship type (WORKS_ON, RELATED_TO, etc.)
    properties: dict[str, Any] = field(default_factory=dict)


class MockGraphDB:
    """
    An in-memory graph database for demo and testing.
    
    Features:
    - Node CRUD operations
    - Relationship management
    - Simple Cypher-like querying
    - Pre-populated with sample entities
    
    Usage:
        graph = MockGraphDB()
        await graph.execute_query(
            "MERGE (e:Person {name: $name})",
            {"name": "john doe"}
        )
    """
    
    # Pre-populated sample entities
    SAMPLE_DATA = {
        "nodes": [
            {"name": "legendstack", "label": "Project", "properties": {"status": "active", "type": "framework"}},
            {"name": "fastapi", "label": "System", "properties": {"type": "web_framework"}},
            {"name": "langgraph", "label": "System", "properties": {"type": "orchestration"}},
            {"name": "neo4j", "label": "System", "properties": {"type": "graph_database"}},
            {"name": "pgvector", "label": "System", "properties": {"type": "vector_database"}},
        ],
        "relationships": [
            {"source": "legendstack", "target": "fastapi", "type": "BUILT_WITH"},
            {"source": "legendstack", "target": "langgraph", "type": "USES"},
            {"source": "legendstack", "target": "neo4j", "type": "INTEGRATES"},
            {"source": "legendstack", "target": "pgvector", "type": "INTEGRATES"},
        ],
    }
    
    def __init__(self):
        """Initialize with sample data."""
        self.nodes: dict[str, MockNode] = {}
        self.relationships: list[MockRelationship] = []
        self._load_sample_data()
    
    def _load_sample_data(self):
        """Load pre-defined sample entities and relationships."""
        for node_data in self.SAMPLE_DATA["nodes"]:
            node = MockNode(
                name=node_data["name"],
                label=node_data["label"],
                properties=node_data.get("properties", {}),
            )
            self.nodes[node.name] = node
        
        for rel_data in self.SAMPLE_DATA["relationships"]:
            rel = MockRelationship(
                source=rel_data["source"],
                target=rel_data["target"],
                type=rel_data["type"],
            )
            self.relationships.append(rel)
        
        logger.info(f"MockGraphDB: Loaded {len(self.nodes)} nodes, {len(self.relationships)} relationships")
    
    async def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Execute a Cypher-like query.
        
        Supports simplified versions of:
        - MERGE (node creation/update)
        - MATCH (node/relationship lookup)
        
        Args:
            cypher: The Cypher query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        params = params or {}
        cypher_upper = cypher.upper()
        
        logger.info(f"MockGraphDB: Executing query with params {params}")
        
        # Handle MERGE operations (create or update)
        if "MERGE" in cypher_upper:
            return await self._handle_merge(cypher, params)
        
        # Handle MATCH operations (read)
        if "MATCH" in cypher_upper:
            return await self._handle_match(cypher, params)
        
        return []
    
    async def _handle_merge(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Handle MERGE operations."""
        name = params.get("name", "").lower()
        if not name:
            return []
        
        # Check if node exists
        if name in self.nodes:
            # Update existing node
            node = self.nodes[name]
            if "properties" in params:
                node.properties.update(params["properties"])
            if "tenant_id" in params:
                node.tenant_id = params["tenant_id"]
            logger.info(f"MockGraphDB: Updated node '{name}'")
        else:
            # Create new node - extract label from query
            label = "Entity"  # Default
            if ":Person" in cypher:
                label = "Person"
            elif ":Project" in cypher:
                label = "Project"
            elif ":System" in cypher:
                label = "System"
            elif ":Organization" in cypher:
                label = "Organization"
            
            node = MockNode(
                name=name,
                label=label,
                properties=params.get("properties", {}),
                tenant_id=params.get("tenant_id"),
            )
            self.nodes[name] = node
            logger.info(f"MockGraphDB: Created node '{name}' with label '{label}'")
        
        return [{"name": name, "label": self.nodes[name].label}]
    
    async def _handle_match(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Handle MATCH operations."""
        results = []
        
        name = params.get("name", "").lower()
        
        # If searching by name
        if name and name in self.nodes:
            node = self.nodes[name]
            
            # Find related entities
            related = []
            for rel in self.relationships:
                if rel.source == name:
                    target_node = self.nodes.get(rel.target)
                    if target_node:
                        related.append({
                            "name": target_node.name,
                            "label": target_node.label,
                            "relationship": rel.type,
                        })
                elif rel.target == name:
                    source_node = self.nodes.get(rel.source)
                    if source_node:
                        related.append({
                            "name": source_node.name,
                            "label": source_node.label,
                            "relationship": rel.type,
                        })
            
            results.append({
                "node": {
                    "name": node.name,
                    "label": node.label,
                    "properties": node.properties,
                },
                "related": related,
            })
        else:
            # Return all nodes if no specific name
            for node in self.nodes.values():
                results.append({
                    "node": {
                        "name": node.name,
                        "label": node.label,
                        "properties": node.properties,
                    },
                })
        
        return results
    
    def get_context_for_entities(self, entity_names: list[str]) -> str:
        """
        Get formatted context string for given entities.
        
        Args:
            entity_names: List of entity names to look up
            
        Returns:
            Formatted context string with entity info and relationships
        """
        context_parts = []
        
        for name in entity_names:
            name_lower = name.lower()
            if name_lower in self.nodes:
                node = self.nodes[name_lower]
                context_parts.append(f"- {node.name} ({node.label}): {node.properties}")
                
                # Add relationships
                for rel in self.relationships:
                    if rel.source == name_lower:
                        context_parts.append(f"  → {rel.type} → {rel.target}")
                    elif rel.target == name_lower:
                        context_parts.append(f"  ← {rel.type} ← {rel.source}")
        
        return "\n".join(context_parts) if context_parts else ""
