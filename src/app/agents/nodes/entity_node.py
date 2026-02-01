"""
Entity Extraction Node.
======================
Extracts key entities (People, Projects, Systems) from messages and persists them in Neo4j.
"""

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langchain_openai import AzureChatOpenAI

from src.app.core import config
from src.app.core.graph_db import GraphDBClient

logger = logging.getLogger(__name__)

class ExtractedEntity(BaseModel):
    """Schema for a single extracted entity."""
    name: str = Field(description="The canonical name of the entity")
    label: str = Field(description="The type of entity (Person, Project, System, Org)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional context or attributes")

class EntityExtractionSchema(BaseModel):
    """Schema for LLM output."""
    entities: List[ExtractedEntity]

class EntityNode:
    """
    LangGraph node responsible for 'remembering' entities.
    """

    def __init__(self, graph_client: GraphDBClient):
        self.graph_client = graph_client
        self.llm = AzureChatOpenAI(
            azure_deployment=config.settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
            openai_api_version=config.settings.AZURE_OPENAI_API_VERSION,
        ).with_structured_output(EntityExtractionSchema)

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts and stores entities from the latest user message.
        """
        if not config.settings.ENABLE_ENTITY_MEMORY:
            return state

        messages = state.get("messages", [])
        if not messages:
            return state

        # Only extract from the last 'user' message to avoid feedback loops
        last_msg = messages[-1]
        if hasattr(last_msg, "role") and last_msg.role != "user":
            return state
        
        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        try:
            logger.info("Extracting entities for memory...")
            result = await self.llm.ainvoke(
                f"Extract key entities (People, Projects, Systems, Organizations) from this text: {content}"
            )

            if result.entities:
                await self._persist_entities(result.entities, state.get("tenant_id"))
                logger.info(f"Stored {len(result.entities)} entities in knowledge graph")

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")

        return state

    async def _persist_entities(self, entities: List[ExtractedEntity], tenant_id: str | None):
        """
        Saves entities to Neo4j using a MERGE operation to avoid duplicates.
        """
        for entity in entities:
            cypher = f"""
            MERGE (e:{entity.label} {{name: $name}})
            ON CREATE SET e.created_at = timestamp(), e.tenant_id = $tenant_id
            SET e += $properties, e.last_seen = timestamp()
            """
            params = {
                "name": entity.name.lower(), # Normalize
                "properties": entity.properties,
                "tenant_id": tenant_id
            }
            await self.graph_client.execute_query(cypher, params)
