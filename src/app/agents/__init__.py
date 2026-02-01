"""
Agentic Building Blocks for the FastAPI Boilerplate.
======================================================

This module provides production-ready components for building AI agents:

Quick Start
-----------
```python
from app.agents import (
    # Core abstractions
    BaseAgent, BaseVectorStore, BaseIndexer, AgentMessage,

    # LLM Services
    LLMService,

    # Vector Stores (plug-and-play)
    VectorStoreFactory, PgVectorStore, AzureAISearchStore,

    # Conversation Management
    ConversationService,

    # Background Tasks
    enqueue_agent_task, get_task_status,

    # Human-in-the-Loop
    HITLManager, hitl_manager,

    # Multi-Tenant
    TenantManager, MultiTenantVectorStore,

    # Observability
    trace_llm_call, trace_vector_operation, trace_agent_execution,
)
```

Architecture
------------
All components follow these principles:
1. **Abstract Base Classes**: Extend BaseAgent, BaseVectorStore, BaseIndexer
2. **Factory Pattern**: Use factories to swap implementations via config
3. **Dependency Injection**: Pass db sessions, services via constructors
4. **Async-First**: All I/O operations are async
5. **Type Safety**: Full type hints and Pydantic models

Creating a Custom Agent
-----------------------
```python
from app.agents import BaseAgent, AgentMessage

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="my_agent", description="Does cool stuff")

    async def invoke(self, input_text: str, config: dict) -> AgentMessage:
        # Your agent logic here
        return AgentMessage(role="assistant", content="Hello!")

    async def stream(self, input_text: str, config: dict):
        yield "Hello "
        yield "World!"
```

Creating a Custom Vector Store
------------------------------
```python
from app.agents import BaseVectorStore

class MyVectorStore(BaseVectorStore):
    async def add_documents(self, documents, ids=None):
        # Store documents
        pass

    async def similarity_search(self, query_vector, k=4, filters=None):
        # Search and return results
        pass

    async def delete_documents(self, ids):
        # Delete by ID
        pass
```

Creating a Custom Indexer
-------------------------
```python
from app.agents import BaseIndexer

class MyDataIndexer(BaseIndexer):
    async def run(self, force=False):
        # Fetch data, embed, store in vector store
        return {"indexed": 100, "source": "my_data"}
```
"""

# Core abstractions
# LLM Services
from .azure_openai import LLMService
from .base import (
    AgentMessage,
    Attachment,
    BaseAgent,
    BaseIndexer,
    BaseVectorStore,
)

# Vector Stores
from .vector_stores import PgVectorStore, VectorStoreFactory

# Try to import optional Azure AI Search (requires azure-search-documents)
try:
    from .azure_search import AzureAISearchStore
except ImportError:
    AzureAISearchStore = None  # type: ignore

# Indexers
from .indexers import DocumentIndexer

# Try to import optional Jira indexer
try:
    from .jira import JiraIndexer
except ImportError:
    JiraIndexer = None  # type: ignore

# Persistence
# Background Tasks
from .background import enqueue_agent_task, get_task_status

# Conversations
from .conversations import ConversationService

# Cost Tracking
from .cost_tracking import LLMCostRecord, calculate_cost, record_llm_cost

# Human-in-the-Loop
from .hitl import HITLManager, HITLRequest, HITLStatus, hitl_manager

# --- Phase 6: Advanced Enhancements ---
# Memory Management
from .memory import BaseMemoryStrategy, MemoryManager, SummarizationStrategy, TruncationStrategy

# Multi-Tenant
from .multi_tenant import MultiTenantVectorStore, TenantManager, current_tenant

# Observability
from .observability import (
    get_tracer,
    setup_telemetry,
    trace_agent_execution,
    trace_llm_call,
    trace_vector_operation,
)
from .persistence import SqlAlchemyCheckpointSaver

# Prompt Versioning
from .prompts import PromptRegistry, PromptVersion, initialize_default_prompts, prompt_registry

# Rate Limiting
from .rate_limiting import (
    RATE_LIMIT_TIERS,
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    RedisRateLimiter,
    TenantRateLimiter,
    UsageStats,
    rate_limiter,
)

# Reranking
from .reranking import BaseReranker, CohereReranker, CrossEncoderReranker, RerankingService

# Resilience
from .resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    ResilientClient,
    RetryConfig,
    retry_with_backoff,
    with_circuit_breaker,
    with_retry,
)

# Sample Agent (for reference)
from .sample_agent import DocAssistantAgent

# Streaming
from .streaming import StreamingChatResponse, sse_stream

# Structured Output
from .structured_output import StructuredOutputError, StructuredOutputValidator, ToolCallValidator

# WebSocket
from .websocket import AgentWSHandler, ConnectionManager, WSMessage, WSMessageType, ws_manager

# Enterprise Indexers
try:
    from .sharepoint import SharePointIndexer
except ImportError:
    SharePointIndexer = None  # type: ignore

try:
    from .confluence import ConfluenceIndexer
except ImportError:
    ConfluenceIndexer = None  # type: ignore

# Version
__version__ = "2.0.0"  # Updated for Phase 6

# Public API
__all__ = [
    # Core
    "AgentMessage",
    "Attachment",
    "BaseAgent",
    "BaseIndexer",
    "BaseVectorStore",
    # LLM
    "LLMService",
    # Vector Stores
    "VectorStoreFactory",
    "PgVectorStore",
    "AzureAISearchStore",
    # Indexers
    "DocumentIndexer",
    "JiraIndexer",
    # Persistence
    "SqlAlchemyCheckpointSaver",
    # Conversations
    "ConversationService",
    # Background
    "enqueue_agent_task",
    "get_task_status",
    # HITL
    "HITLManager",
    "HITLRequest",
    "HITLStatus",
    "hitl_manager",
    # Multi-Tenant
    "TenantManager",
    "MultiTenantVectorStore",
    "current_tenant",
    # Streaming
    "StreamingChatResponse",
    "sse_stream",
    # Observability
    "setup_telemetry",
    "get_tracer",
    "trace_llm_call",
    "trace_vector_operation",
    "trace_agent_execution",
    # Cost
    "LLMCostRecord",
    "calculate_cost",
    "record_llm_cost",
    # Sample
    "DocAssistantAgent",
]


# =============================================================================
# Component Registry (for dynamic discovery and extension)
# =============================================================================


class ComponentRegistry:
    """
    Registry for dynamically discovering and registering agent components.

    Usage:
        # Register a custom vector store
        from app.agents import registry
        registry.register_vector_store("pinecone", PineconeVectorStore)

        # Get a registered component
        store_class = registry.get_vector_store("pinecone")
    """

    def __init__(self):
        self._vector_stores: dict[str, type] = {}
        self._indexers: dict[str, type] = {}
        self._agents: dict[str, type] = {}

        # Register built-in components
        self._register_defaults()

    def _register_defaults(self):
        """Register default built-in components."""
        self._vector_stores["pgvector"] = PgVectorStore
        if AzureAISearchStore:
            self._vector_stores["azure_search"] = AzureAISearchStore  # type: ignore

        self._indexers["document"] = DocumentIndexer
        if JiraIndexer:
            self._indexers["jira"] = JiraIndexer  # type: ignore

        self._agents["doc_assistant"] = DocAssistantAgent

    # Vector Stores
    def register_vector_store(self, name: str, cls: type) -> None:
        """Register a custom vector store implementation."""
        if not issubclass(cls, BaseVectorStore):
            raise TypeError(f"{cls} must extend BaseVectorStore")
        self._vector_stores[name] = cls

    def get_vector_store(self, name: str) -> type | None:
        """Get a registered vector store class by name."""
        return self._vector_stores.get(name)

    def list_vector_stores(self) -> list[str]:
        """List all registered vector store names."""
        return list(self._vector_stores.keys())

    # Indexers
    def register_indexer(self, name: str, cls: type) -> None:
        """Register a custom indexer implementation."""
        if not issubclass(cls, BaseIndexer):
            raise TypeError(f"{cls} must extend BaseIndexer")
        self._indexers[name] = cls

    def get_indexer(self, name: str) -> type | None:
        """Get a registered indexer class by name."""
        return self._indexers.get(name)

    def list_indexers(self) -> list[str]:
        """List all registered indexer names."""
        return list(self._indexers.keys())

    # Agents
    def register_agent(self, name: str, cls: type) -> None:
        """Register a custom agent implementation."""
        if not issubclass(cls, BaseAgent):
            raise TypeError(f"{cls} must extend BaseAgent")
        self._agents[name] = cls

    def get_agent(self, name: str) -> type | None:
        """Get a registered agent class by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())


# Global registry instance
registry = ComponentRegistry()
