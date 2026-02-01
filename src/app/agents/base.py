from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """Represents a file or reference attached to a message."""

    id: str
    name: str
    content_type: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentMessage(BaseModel):
    """Standard message format for agent communication."""

    role: str  # user, assistant, system, tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseVectorStore(ABC):
    """Abstract interface for Vector Store backends (pgvector, Azure AI Search, etc.)"""

    @abstractmethod
    async def add_documents(self, documents: list[dict[str, Any]], ids: list[str] | None = None) -> list[str]:
        """Add documents (text + embeddings) to the store."""
        pass

    @abstractmethod
    async def similarity_search(
        self, query_vector: list[float], k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Perform similarity search with optional metadata filtering."""
        pass

    @abstractmethod
    async def delete_documents(self, ids: list[str]) -> None:
        """Remove documents by ID."""
        pass


class BaseIndexer(ABC):
    """Abstract interface for data source indexers (Jira, Product Docs, etc.)"""

    @abstractmethod
    async def run(self, force: bool = False) -> dict[str, Any]:
        """Run the indexing process (incremental by default)."""
        pass


class BaseAgent(ABC):
    """Abstract base class for all Agentic solutions."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def invoke(self, input_text: str, config: dict[str, Any]) -> AgentMessage:
        """Invoke the agent for a single blocking response."""
        pass

    @abstractmethod
    async def stream(self, input_text: str, config: dict[str, Any]) -> AsyncGenerator[str | dict[str, Any], None]:
        """Stream the agent response (token-by-token or node-by-node)."""
        pass
