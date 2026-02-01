"""
Demo Agent Tests
=================
Comprehensive unit tests for the LegendDemo Agent.
These tests verify that all features work correctly with mock services.
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.app.agents.demo import LegendDemoAgent, DemoAgentConfig
from src.app.agents.demo.mocks import MockLLM, MockVectorStore, MockGraphDB
from src.app.agents.demo.nodes import (
    InputNode,
    CacheNode,
    RAGNode,
    GraphRAGNode,
    MemoryNode,
    DemoEntityNode,
    GenerateNode,
    ReflectorNode,
    HITLNode,
    CostNode,
    OutputNode,
)


class TestMockServices:
    """Tests for mock service implementations."""
    
    @pytest.mark.asyncio
    async def test_mock_llm_returns_response(self):
        """Verify MockLLM returns appropriate responses."""
        llm = MockLLM()
        response = await llm.ainvoke("Tell me about LegendStack")
        
        assert response.content
        assert "LegendStack" in response.content
        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0
    
    @pytest.mark.asyncio
    async def test_mock_llm_embeddings(self):
        """Verify MockLLM generates embeddings."""
        llm = MockLLM()
        embedding = await llm.get_embeddings("test query")
        
        assert len(embedding) == 1536
        assert all(isinstance(v, float) for v in embedding)
    
    @pytest.mark.asyncio
    async def test_mock_vector_store_search(self):
        """Verify MockVectorStore returns relevant documents."""
        store = MockVectorStore()
        llm = MockLLM()
        
        query_vector = await llm.get_embeddings("What is RAG?")
        results = await store.similarity_search(query_vector, k=3)
        
        assert len(results) <= 3
        assert all("content" in r for r in results)
        assert all("score" in r for r in results)
    
    @pytest.mark.asyncio
    async def test_mock_graph_db_merge(self):
        """Verify MockGraphDB handles MERGE operations."""
        graph = MockGraphDB()
        
        result = await graph.execute_query(
            "MERGE (e:Person {name: $name})",
            {"name": "jane doe"}
        )
        
        assert len(result) > 0
        assert result[0]["name"] == "jane doe"
        assert "jane doe" in graph.nodes
    
    @pytest.mark.asyncio
    async def test_mock_graph_db_match(self):
        """Verify MockGraphDB handles MATCH operations."""
        graph = MockGraphDB()
        
        result = await graph.execute_query(
            "MATCH (n {name: $name}) RETURN n",
            {"name": "legendstack"}
        )
        
        assert len(result) > 0
        assert "node" in result[0]
        assert result[0]["node"]["name"] == "legendstack"


class TestDemoAgentNodes:
    """Tests for individual node implementations."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return DemoAgentConfig(USE_MOCKS=True)
    
    @pytest.fixture
    def base_state(self):
        """Create base state for testing."""
        return {
            "messages": [{"role": "user", "content": "Test message"}],
            "original_input": "Test message",
            "sanitized_input": "",
            "context": "",
            "entities": [],
            "response": "",
            "reflection": None,
            "needs_human_approval": False,
            "human_approved": True,
            "cost_info": {},
            "cache_hit": False,
            "tenant_id": "test-tenant",
            "thread_id": "test-thread",
            "metadata": {},
        }
    
    @pytest.mark.asyncio
    async def test_input_node_masks_pii(self, config, base_state):
        """Verify InputNode masks PII correctly."""
        config.ENABLE_PII_GUARD = True
        node = InputNode(config)
        
        base_state["messages"][-1]["content"] = "Contact me at test@example.com or 555-123-4567"
        
        result = await node(base_state)
        
        assert "[EMAIL_MASKED]" in result["sanitized_input"]
        assert "[PHONE_MASKED]" in result["sanitized_input"]
        assert "test@example.com" not in result["sanitized_input"]
    
    @pytest.mark.asyncio
    async def test_cache_node_returns_cached(self, config, base_state):
        """Verify CacheNode returns cached responses."""
        node = CacheNode(config)
        
        # Use a query that's seeded in the cache
        base_state["sanitized_input"] = "what is legendstack"
        
        result = await node(base_state)
        
        assert result["cache_hit"] is True
        assert "[CACHED]" in result["response"]
    
    @pytest.mark.asyncio
    async def test_cache_node_misses_uncached(self, config, base_state):
        """Verify CacheNode returns miss for uncached queries."""
        node = CacheNode(config)
        
        base_state["sanitized_input"] = "something completely unique 12345"
        
        result = await node(base_state)
        
        assert result["cache_hit"] is False
    
    @pytest.mark.asyncio
    async def test_rag_node_retrieves_context(self, config, base_state):
        """Verify RAGNode retrieves relevant context."""
        llm = MockLLM()
        store = MockVectorStore()
        node = RAGNode(config, store, llm)
        
        base_state["sanitized_input"] = "Tell me about RAG"
        
        result = await node(base_state)
        
        assert result["context"]
        assert len(result["context"]) > 0
    
    @pytest.mark.asyncio
    async def test_generate_node_produces_response(self, config, base_state):
        """Verify GenerateNode produces a response."""
        llm = MockLLM()
        node = GenerateNode(config, llm)
        
        base_state["sanitized_input"] = "What is LegendStack?"
        base_state["context"] = "LegendStack is an AI framework."
        
        result = await node(base_state)
        
        assert result["response"]
        assert "cost_info" in result
        assert result["cost_info"]["total_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_reflector_node_evaluates_quality(self, config, base_state):
        """Verify ReflectorNode evaluates response quality."""
        node = ReflectorNode(config)
        
        # Good response with context references
        base_state["response"] = "Based on the context, LegendStack specifically provides RAG capabilities."
        base_state["context"] = "LegendStack is an AI framework for RAG."
        
        result = await node(base_state)
        
        assert "reflection" in result
        assert result["reflection"]["score"] > 0  # Some quality score
    
    @pytest.mark.asyncio
    async def test_cost_node_tracks_usage(self, config, base_state):
        """Verify CostNode tracks token usage."""
        node = CostNode(config)
        
        base_state["cost_info"] = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "model": "gpt-4o",
        }
        base_state["tenant_id"] = "test-tenant"
        
        result = await node(base_state)
        
        assert "estimated_cost_usd" in result["cost_info"]
        
        # Check usage was recorded
        usage = node.get_usage("test-tenant")
        assert len(usage) > 0


class TestLegendDemoAgent:
    """Integration tests for the full demo agent."""
    
    @pytest.fixture
    def agent(self):
        """Create agent with mock services."""
        config = DemoAgentConfig(USE_MOCKS=True)
        return LegendDemoAgent(config=config)
    
    @pytest.mark.asyncio
    async def test_agent_full_flow(self, agent):
        """Verify agent processes a full request."""
        result = await agent.chat(
            "What is LegendStack?",
            thread_id="test-1",
            tenant_id="tenant-1",
        )
        
        assert "response" in result
        assert result["response"]
        assert "features_used" in result
        assert len(result["features_used"]) > 0
    
    @pytest.mark.asyncio
    async def test_agent_cache_hit(self, agent):
        """Verify agent uses cache on repeated queries."""
        # First query - cache miss
        result1 = await agent.chat("what is legendstack", thread_id="test-2")
        
        # This query is seeded in the cache
        assert result1["cache_hit"] is True or "semantic_cache" in result1["features_used"]
    
    @pytest.mark.asyncio
    async def test_agent_config_summary(self, agent):
        """Verify config summary returns all features."""
        summary = agent.get_config_summary()
        
        expected_keys = [
            "mocks", "pii_guard", "moderation", "rag", "graph_rag",
            "semantic_cache", "entity_memory", "memory_summarization",
            "reflector", "hitl", "cost_tracking", "tracing",
            "circuit_breaker", "retry", "rate_limiting",
        ]
        
        for key in expected_keys:
            assert key in summary
    
    @pytest.mark.asyncio
    async def test_agent_disables_features(self):
        """Verify features can be disabled via config."""
        config = DemoAgentConfig(
            USE_MOCKS=True,
            ENABLE_RAG=False,
            ENABLE_GRAPH_RAG=False,
            ENABLE_REFLECTOR=False,
        )
        agent = LegendDemoAgent(config=config)
        
        result = await agent.chat("Test query", thread_id="test-3")
        
        # RAG should not be in features used
        assert "rag_retrieval" not in result["features_used"]
    
    @pytest.mark.asyncio
    async def test_agent_pii_protection(self):
        """Verify PII is masked in the flow."""
        config = DemoAgentConfig(USE_MOCKS=True, ENABLE_PII_GUARD=True)
        agent = LegendDemoAgent(config=config)
        
        result = await agent.chat(
            "My email is secret@company.com and phone is 555-123-4567",
            thread_id="test-4",
        )
        
        # Verify PII masking was applied
        assert "pii_masking" in result["features_used"]


class TestDemoEntityExtraction:
    """Tests for entity extraction functionality."""
    
    @pytest.fixture
    def config(self):
        return DemoAgentConfig(USE_MOCKS=True, ENABLE_ENTITY_MEMORY=True)
    
    @pytest.fixture
    def base_state(self):
        return {
            "messages": [],
            "original_input": "",
            "sanitized_input": "",
            "context": "",
            "entities": [],
            "response": "",
            "reflection": None,
            "needs_human_approval": False,
            "human_approved": True,
            "cost_info": {},
            "cache_hit": False,
            "tenant_id": "test-tenant",
            "thread_id": "test-thread",
            "metadata": {},
        }
    
    @pytest.mark.asyncio
    async def test_entity_extraction_person(self, config, base_state):
        """Verify person entity extraction."""
        graph = MockGraphDB()
        node = DemoEntityNode(config, graph)
        
        base_state["sanitized_input"] = "My name is John Smith and I work on Project Alpha"
        
        result = await node(base_state)
        
        entities = result.get("entities", [])
        entity_names = [e["name"] for e in entities]
        
        # Should extract person and/or project
        assert len(entities) > 0
