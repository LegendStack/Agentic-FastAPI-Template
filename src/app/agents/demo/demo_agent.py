"""
LegendDemo Agent - Comprehensive Feature Showcase
==================================================
A modular, educational agent that demonstrates ALL features of the LegendStack framework.

This agent is designed to:
1. Run out-of-the-box with mock services (no external dependencies)
2. Showcase every major feature
3. Be modular so features can be toggled on/off
4. Serve as a learning reference for developers

Features Demonstrated:
- LangGraph orchestration with conditional routing
- RAG (Vector Search)
- Graph-RAG (Neo4j relationships)
- Entity-Aware Memory (V4.1)
- Semantic Caching (V4.0)
- Self-Correction / Reflector (V4.0)
- Safety Guardrails (PII, Moderation)
- Resilience (Retry, Circuit Breaker)
- Rate Limiting
- Cost Tracking
- HITL (Human-in-the-Loop)
- Observability / Tracing

Usage:
    from app.agents.demo import LegendDemoAgent, DemoAgentConfig

    # Create with all mocks (zero dependencies)
    agent = LegendDemoAgent()

    # Or with custom config
    config = DemoAgentConfig(ENABLE_HITL=True)
    agent = LegendDemoAgent(config=config)

    # Chat
    response = await agent.chat("What is LegendStack?", thread_id="demo-1")
    print(response)
"""

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from .config import DemoAgentConfig
from .mocks import MockGraphDB, MockLLM, MockVectorStore
from .nodes import (
    CacheNode,
    CostNode,
    DemoEntityNode,
    GenerateNode,
    GraphRAGNode,
    HITLNode,
    InputNode,
    MemoryNode,
    OutputNode,
    RAGNode,
    ReflectorNode,
)
from .state import DemoAgentState

logger = logging.getLogger(__name__)


class LegendDemoAgent:
    """
    The LegendDemo Agent - a comprehensive feature showcase.

    This agent demonstrates all capabilities of the LegendStack framework
    in a single, modular, and educational implementation.

    Attributes:
        config: Feature toggles and settings
        graph: The compiled LangGraph workflow

    Example:
        >>> agent = LegendDemoAgent()
        >>> result = await agent.chat("Tell me about RAG")
        >>> print(result["response"])
    """

    def __init__(self, config: DemoAgentConfig | None = None):
        """
        Initialize the demo agent.

        Args:
            config: Optional configuration. Defaults to all features enabled with mocks.
        """
        self.config = config or DemoAgentConfig()

        # Initialize services (mock or real)
        self._init_services()

        # Initialize nodes
        self._init_nodes()

        # Build graph
        self.graph = self._build_graph()

        logger.info(f"LegendDemoAgent initialized (USE_MOCKS={self.config.USE_MOCKS})")

    def _init_services(self):
        """Initialize mock or real services based on config."""
        if self.config.USE_MOCKS:
            logger.info("Using MOCK services (zero external dependencies)")
            self.llm = MockLLM()
            self.vector_store = MockVectorStore()
            self.graph_db = MockGraphDB()
        else:
            # In production, you would initialize real services here
            # from ..azure_openai import get_azure_openai_chat
            # from ..vector_stores import VectorStoreFactory
            # from ...core.graph_db import GraphDBClient
            raise NotImplementedError(
                "Real services not yet wired. Set USE_MOCKS=True or implement real service initialization."
            )

    def _init_nodes(self):
        """Initialize all workflow nodes."""
        # Safety & Input
        self.input_node = InputNode(self.config)

        # Caching
        self.cache_node = CacheNode(self.config)

        # Retrieval
        self.rag_node = RAGNode(self.config, self.vector_store, self.llm)
        self.graph_rag_node = GraphRAGNode(self.config, self.graph_db)

        # Memory
        self.memory_node = MemoryNode(self.config)
        self.entity_node = DemoEntityNode(self.config, self.graph_db)

        # Generation
        self.generate_node = GenerateNode(self.config, self.llm)

        # Quality
        self.reflector_node = ReflectorNode(self.config)

        # Governance
        self.hitl_node = HITLNode(self.config)

        # Observability
        self.cost_node = CostNode(self.config)

        # Output
        self.output_node = OutputNode(self.config, self.cache_node)

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with conditional routing.

        Flow:
        START → input → cache_check
            ↓ (cache hit) → output → END
            ↓ (cache miss) → rag → graph_rag → memory → entity → generate
                → reflector_check
                    ↓ (needs reflection) → generate (loop)
                    ↓ (good) → hitl → cost → output → END
        """
        workflow = StateGraph(DemoAgentState)

        # === Add Nodes ===
        workflow.add_node("input", self.input_node)
        workflow.add_node("cache_check", self.cache_node)
        workflow.add_node("rag", self.rag_node)
        workflow.add_node("graph_rag", self.graph_rag_node)
        workflow.add_node("memory", self.memory_node)
        workflow.add_node("entity", self.entity_node)
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("reflector", self.reflector_node)
        workflow.add_node("hitl", self.hitl_node)
        workflow.add_node("cost", self.cost_node)
        workflow.add_node("output", self.output_node)

        # === Define Edges ===

        # Entry point
        workflow.add_edge(START, "input")
        workflow.add_edge("input", "cache_check")

        # Cache routing
        workflow.add_conditional_edges(
            "cache_check",
            self._route_after_cache,
            {
                "cached": "output",
                "not_cached": "rag",
            },
        )

        # Retrieval chain
        workflow.add_edge("rag", "graph_rag")
        workflow.add_edge("graph_rag", "memory")
        workflow.add_edge("memory", "entity")
        workflow.add_edge("entity", "generate")
        workflow.add_edge("generate", "reflector")

        # Reflector routing
        workflow.add_conditional_edges(
            "reflector",
            self._route_after_reflector,
            {
                "reflect": "generate",
                "proceed": "hitl",
            },
        )

        # Final chain
        workflow.add_edge("hitl", "cost")
        workflow.add_edge("cost", "output")
        workflow.add_edge("output", END)

        return workflow.compile()

    def _route_after_cache(self, state: DemoAgentState) -> Literal["cached", "not_cached"]:
        """Route based on cache hit."""
        if state.get("cache_hit", False):
            logger.info("Routing: Cache HIT → output")
            return "cached"
        logger.info("Routing: Cache MISS → rag")
        return "not_cached"

    def _route_after_reflector(self, state: DemoAgentState) -> Literal["reflect", "proceed"]:
        """Route based on reflection decision."""
        reflection = state.get("reflection") or {}
        if reflection.get("needed", False) and reflection.get("attempt", 0) < 2:
            logger.info(f"Routing: Reflection needed (attempt {reflection.get('attempt')})")
            return "reflect"
        logger.info("Routing: Quality OK → hitl")
        return "proceed"

    async def chat(
        self,
        user_input: str,
        thread_id: str = "default",
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message through the agent.

        Args:
            user_input: The user's message
            thread_id: Conversation thread identifier
            tenant_id: Optional tenant for multi-tenancy

        Returns:
            Dictionary with response and metadata
        """
        logger.info("=== LegendDemo Agent: New Request ===")
        logger.info(f"Thread: {thread_id}, Tenant: {tenant_id or 'N/A'}")

        # Initialize state
        initial_state: DemoAgentState = {
            "messages": [{"role": "user", "content": user_input}],
            "original_input": user_input,
            "sanitized_input": "",
            "context": "",
            "entities": [],
            "response": "",
            "reflection": None,
            "needs_human_approval": False,
            "human_approved": True,
            "cost_info": {},
            "cache_hit": False,
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "metadata": {},
        }

        # Run graph
        final_state = None
        async for event in self.graph.astream(initial_state, stream_mode="values"):
            final_state = event

        # Extract result
        metadata = final_state.get("metadata") or {}
        result = {
            "response": final_state.get("response", "No response generated"),
            "thread_id": thread_id,
            "cache_hit": final_state.get("cache_hit", False),
            "features_used": metadata.get("features_used", []),
            "cost_info": final_state.get("cost_info", {}),
            "entities_extracted": final_state.get("entities", []),
        }

        logger.info("=== LegendDemo Agent: Complete ===")
        logger.info(f"Features used: {result['features_used']}")

        return result

    def get_config_summary(self) -> dict[str, bool]:
        """Get a summary of enabled features."""
        return {
            "mocks": self.config.USE_MOCKS,
            "pii_guard": self.config.ENABLE_PII_GUARD,
            "moderation": self.config.ENABLE_MODERATION,
            "rag": self.config.ENABLE_RAG,
            "graph_rag": self.config.ENABLE_GRAPH_RAG,
            "semantic_cache": self.config.ENABLE_SEMANTIC_CACHE,
            "entity_memory": self.config.ENABLE_ENTITY_MEMORY,
            "memory_summarization": self.config.ENABLE_MEMORY_SUMMARIZATION,
            "reflector": self.config.ENABLE_REFLECTOR,
            "hitl": self.config.ENABLE_HITL,
            "cost_tracking": self.config.ENABLE_COST_TRACKING,
            "tracing": self.config.ENABLE_TRACING,
            "circuit_breaker": self.config.ENABLE_CIRCUIT_BREAKER,
            "retry": self.config.ENABLE_RETRY,
            "rate_limiting": self.config.ENABLE_RATE_LIMITING,
        }


# === CLI Demo Runner ===
if __name__ == "__main__":
    import asyncio

    async def demo():
        """Run a quick demo of the agent."""
        print("\n" + "=" * 60)
        print("🚀 LegendDemo Agent - Feature Showcase")
        print("=" * 60 + "\n")

        # Create agent with all defaults (mocks enabled)
        agent = LegendDemoAgent()

        # Show config
        print("📋 Enabled Features:")
        for feature, enabled in agent.get_config_summary().items():
            status = "✅" if enabled else "❌"
            print(f"   {status} {feature}")
        print()

        # Test queries
        test_queries = [
            "What is LegendStack?",
            "How does RAG work?",  # This should hit cache on second run
            "Tell me about security features",
        ]

        for query in test_queries:
            print(f"\n💬 User: {query}")
            print("-" * 40)

            result = await agent.chat(query, thread_id="demo-session")

            print(f"🤖 Agent: {result['response'][:200]}...")
            print(f"   📊 Features: {', '.join(result['features_used'])}")
            if result.get("cache_hit"):
                print("   ⚡ (Served from cache!)")
            print()

        print("\n" + "=" * 60)
        print("✅ Demo Complete!")
        print("=" * 60)

    asyncio.run(demo())
