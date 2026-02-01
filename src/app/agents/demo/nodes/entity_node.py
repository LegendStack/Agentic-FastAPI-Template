"""
Entity Node - Entity Extraction & Memory
=========================================
Extracts entities (people, projects, systems) from conversations.
Stores them in the graph database for cross-thread recall.

This demonstrates the Entity-Aware Memory feature (V4.1).
"""

import logging
import re
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState
from ..mocks import MockGraphDB

logger = logging.getLogger(__name__)


class DemoEntityNode:
    """
    Entity extraction and storage node.
    
    Features:
    - Pattern-based entity extraction (simplified for demo)
    - Graph DB storage with tenant isolation
    - Cross-thread entity recall
    
    In production, this uses LLM-based extraction.
    
    Usage:
        node = DemoEntityNode(config, graph_db)
        new_state = await node(state)
    """
    
    # Patterns for entity extraction (simplified)
    ENTITY_PATTERNS = {
        "Person": [
            r"(?:my name is|i am|call me|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:told me|said|mentioned|asked)",
        ],
        "Project": [
            r"(?:project|working on|building)\s+([A-Z][a-zA-Z0-9-_]+)",
            r"([A-Z][a-zA-Z0-9-_]+)\s+(?:project|app|application|system)",
        ],
        "Organization": [
            r"(?:at|work for|from)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)",
        ],
    }
    
    def __init__(self, config: DemoAgentConfig, graph_db: MockGraphDB | Any):
        """Initialize with dependencies."""
        self.config = config
        self.graph_db = graph_db
    
    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Extract and store entities from user input.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with extracted entities
        """
        if not self.config.ENABLE_ENTITY_MEMORY:
            logger.info("EntityNode: Entity memory disabled, skipping")
            return {"entities": []}
        
        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("EntityNode: Skipping due to cache hit")
            return {}
        
        user_input = state.get("sanitized_input", state.get("original_input", ""))
        tenant_id = state.get("tenant_id")
        
        logger.info("EntityNode: Extracting entities from input")
        
        # Extract entities
        extracted_entities = self._extract_entities(user_input)
        
        # Store in graph DB
        for entity in extracted_entities:
            try:
                await self.graph_db.execute_query(
                    f"MERGE (e:{entity['type']} {{name: $name}})",
                    {
                        "name": entity["name"],
                        "properties": entity.get("properties", {}),
                        "tenant_id": tenant_id,
                    }
                )
                logger.info(f"EntityNode: Stored entity '{entity['name']}' ({entity['type']})")
            except Exception as e:
                logger.error(f"EntityNode: Failed to store entity - {e}")
        
        # Also get context from existing entities
        entity_names = [e["name"] for e in extracted_entities]
        graph_context = self.graph_db.get_context_for_entities(entity_names)
        
        current_context = state.get("context", "")
        if graph_context:
            enriched = current_context + f"\n\n🧠 Entity Memory:\n{graph_context}"
            return {"entities": extracted_entities, "context": enriched}
        
        return {"entities": extracted_entities}
    
    def _extract_entities(self, text: str) -> list[dict[str, Any]]:
        """
        Extract entities using pattern matching.
        
        In production, this would use LLM-based extraction.
        """
        entities = []
        
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Skip common words
                    if match.lower() in ["i", "the", "a", "an", "my"]:
                        continue
                    entities.append({
                        "name": match.lower(),
                        "type": entity_type,
                        "source": "pattern_extraction",
                    })
        
        # Deduplicate
        seen = set()
        unique_entities = []
        for entity in entities:
            key = (entity["name"], entity["type"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)
        
        if unique_entities:
            logger.info(f"EntityNode: Extracted {len(unique_entities)} entities")
        
        return unique_entities
