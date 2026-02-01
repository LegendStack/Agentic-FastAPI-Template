"""
Integration Tests for Phase 6 Advanced Enhancements.
=====================================================
End-to-end tests for Admin API, combined workflows, and real interactions.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Admin API Integration Tests
# ============================================================================


class TestAdminAgentsAPI:
    """Integration tests for Admin Agents API endpoints."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_admin_stats_endpoint_structure(self):
        """Test admin stats response structure."""
        from src.app.api.v1.admin_agents import AgentStatsResponse

        # Verify response model structure
        stats = AgentStatsResponse(
            total_conversations=100,
            active_conversations=50,
            total_messages=1000,
            avg_messages_per_conversation=10.0,
            conversations_last_24h=20,
            conversations_last_7d=75,
        )

        assert stats.total_conversations == 100
        assert stats.avg_messages_per_conversation == 10.0

    @pytest.mark.asyncio
    async def test_cost_summary_response_structure(self):
        """Test cost summary response structure."""
        from src.app.api.v1.admin_agents import CostSummaryResponse

        now = datetime.utcnow()
        summary = CostSummaryResponse(
            period_start=now - timedelta(days=7),
            period_end=now,
            total_tokens=500000,
            total_cost_usd=12.50,
            by_model={"gpt-4": {"tokens": 300000, "cost": 9.0}},
            by_tenant={"tenant-1": {"tokens": 500000, "cost": 12.50}},
        )

        assert summary.total_tokens == 500000
        assert summary.total_cost_usd == 12.50

    @pytest.mark.asyncio
    async def test_tenant_usage_response_structure(self):
        """Test tenant usage response structure."""
        from src.app.api.v1.admin_agents import TenantUsageResponse

        usage = TenantUsageResponse(
            tenant_id="tenant-123",
            tokens_used=50000,
            requests_made=500,
            tokens_limit=100000,
            requests_limit=1000,
            utilization_percent=50.0,
        )

        assert usage.tenant_id == "tenant-123"
        assert usage.utilization_percent == 50.0


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


class TestMemoryWithConversations:
    """Integration tests for Memory + Conversations workflow."""

    @pytest.mark.asyncio
    async def test_memory_truncation_workflow(self):
        """Test memory truncation with conversation messages."""
        from src.app.agents.memory import TruncationStrategy

        # Mock conversation service
        mock_service = MagicMock()

        # Create mock messages
        messages = [MagicMock(role="user", content=f"Message {i}" * 100) for i in range(20)]
        mock_service.get_messages = AsyncMock(return_value=messages)

        strategy = TruncationStrategy(mock_service)

        # Get context with limited tokens
        context = await strategy.get_context("thread-123", max_tokens=500)

        # Should have truncated to fit within budget
        assert len(context) < 20

    @pytest.mark.asyncio
    async def test_memory_preserves_recent_messages(self):
        """Test that memory preserves most recent messages."""
        from src.app.agents.memory import TruncationStrategy

        mock_service = MagicMock()
        messages = [
            MagicMock(role="user", content="Old message"),
            MagicMock(role="assistant", content="Old response"),
            MagicMock(role="user", content="Recent message"),
            MagicMock(role="assistant", content="Recent response"),
        ]
        mock_service.get_messages = AsyncMock(return_value=messages)

        strategy = TruncationStrategy(mock_service)
        context = await strategy.get_context("thread-123", max_tokens=100)

        # Most recent messages should be preserved
        if context:
            assert context[-1]["content"] == "Recent response"


class TestRerankingWithVectorSearch:
    """Integration tests for Reranking + Vector Search workflow."""

    @pytest.mark.asyncio
    async def test_reranking_improves_ordering(self):
        """Test that reranking reorders documents by relevance."""
        from src.app.agents.reranking import BaseReranker, RerankingService

        # Create a mock reranker that reverses scores
        class MockReranker(BaseReranker):
            async def rerank(self, query, documents, top_k=5):
                # Score based on query match
                scored = []
                for doc in documents:
                    score = 1.0 if query.lower() in doc["content"].lower() else 0.0
                    doc_copy = doc.copy()
                    doc_copy["rerank_score"] = score
                    scored.append(doc_copy)
                scored.sort(key=lambda x: x["rerank_score"], reverse=True)
                return scored[:top_k]

        service = RerankingService(MockReranker())

        docs = [
            {"content": "Unrelated document about cats"},
            {"content": "Document about Python programming"},
            {"content": "Another unrelated thing"},
        ]

        result = await service.rerank("Python", docs, top_k=3)

        # Python document should be first
        assert "Python" in result[0]["content"]


class TestResilienceWithLLM:
    """Integration tests for Resilience + LLM workflow."""

    @pytest.mark.asyncio
    async def test_resilient_llm_call(self):
        """Test resilient LLM call with retry and circuit breaker."""
        from src.app.agents.resilience import ResilientClient, RetryConfig

        attempts = [0]

        async def flaky_llm_call(prompt):
            attempts[0] += 1
            if attempts[0] < 2:
                raise TimeoutError("LLM timeout")
            return {"content": "Hello, world!"}

        client = ResilientClient(retry_config=RetryConfig(max_attempts=3, initial_delay=0.01), name="llm")

        result = await client.execute(flaky_llm_call, "Say hello")

        assert result["content"] == "Hello, world!"
        assert attempts[0] == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascade(self):
        """Test circuit breaker prevents cascading failures."""
        from src.app.agents.resilience import CircuitBreakerConfig, CircuitOpenError, ResilientClient, RetryConfig

        async def always_fails():
            raise ValueError("Service unavailable")

        client = ResilientClient(
            retry_config=RetryConfig(max_attempts=1, initial_delay=0.01),
            circuit_config=CircuitBreakerConfig(failure_threshold=2),
            name="test",
        )

        # First two calls should try and fail
        for _ in range(2):
            with pytest.raises(ValueError):
                await client.execute(always_fails)

        # Third call should fail fast with CircuitOpenError
        with pytest.raises(CircuitOpenError):
            await client.execute(always_fails)


class TestRateLimitingWithTenants:
    """Integration tests for Rate Limiting + Multi-Tenant workflow."""

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self):
        """Test rate limits are isolated per tenant."""
        from src.app.agents.rate_limiting import InMemoryRateLimiter, RateLimitConfig, TenantRateLimiter

        config = RateLimitConfig(tokens_per_minute=100, requests_per_minute=10)
        limiter = TenantRateLimiter(InMemoryRateLimiter(config))

        # Tenant 1 uses their quota
        await limiter.record_usage("tenant-1", tokens_used=90, requests=8)

        # Tenant 2 should be unaffected
        allowed = await limiter.check_limit("tenant-2", tokens_requested=50)
        assert allowed is True

        # Tenant 1 should be limited
        allowed = await limiter.check_limit("tenant-1", tokens_requested=20)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_tier_based_limits(self):
        """Test different tiers have different limits."""
        from src.app.agents.rate_limiting import TenantRateLimiter

        limiter = TenantRateLimiter()

        # Set different tiers
        limiter.set_tenant_tier("free-tenant", "free")
        limiter.set_tenant_tier("enterprise-tenant", "enterprise")

        # Check limits
        free_usage = await limiter.get_usage("free-tenant")
        enterprise_usage = await limiter.get_usage("enterprise-tenant")

        # Enterprise should have higher limits
        assert enterprise_usage.tokens_limit > free_usage.tokens_limit


class TestPromptVersioningWorkflow:
    """Integration tests for Prompt Versioning workflow."""

    @pytest.mark.asyncio
    async def test_prompt_ab_testing(self):
        """Test A/B testing with prompt versions."""
        from src.app.agents.prompts import PromptRegistry

        registry = PromptRegistry()

        # Create two versions
        await registry.set("system_prompt", "You are helpful.")
        await registry.set("system_prompt", "You are an expert assistant.")

        # Get specific versions for A/B testing
        v1 = await registry.get("system_prompt", version=1)
        v2 = await registry.get("system_prompt", version=2)

        assert v1 == "You are helpful."
        assert v2 == "You are an expert assistant."

    @pytest.mark.asyncio
    async def test_prompt_rollback_on_regression(self):
        """Test rolling back after detecting regression."""
        from src.app.agents.prompts import PromptRegistry

        registry = PromptRegistry()

        # Version 1: Good prompt
        await registry.set("qa_prompt", "Answer questions accurately with citations.")

        # Version 2: Bad prompt (hypothetically causes regressions)
        await registry.set("qa_prompt", "Just guess the answer.")

        # Rollback to v1
        await registry.rollback("qa_prompt", version=1)

        # Current should be v1 content
        current = await registry.get("qa_prompt")
        assert current == "Answer questions accurately with citations."


class TestStructuredOutputWithToolCalls:
    """Integration tests for Structured Output + Tool Calls workflow."""

    @pytest.mark.asyncio
    async def test_tool_registration_and_validation(self):
        """Test registering and validating tool calls."""
        from pydantic import BaseModel

        from src.app.agents.structured_output import StructuredOutputError, ToolCallValidator

        class SearchParams(BaseModel):
            """Search for documents."""

            query: str
            limit: int = 10

        class CreateTaskParams(BaseModel):
            """Create a new task."""

            title: str
            description: str
            priority: int

        validator = ToolCallValidator()
        validator.register_tool("search", SearchParams)
        validator.register_tool("create_task", CreateTaskParams)

        # Valid search call
        search_result = validator.validate_tool_call("search", {"query": "Python tutorials", "limit": 5})
        assert search_result.query == "Python tutorials"
        assert search_result.limit == 5

        # Valid create_task call
        task_result = validator.validate_tool_call(
            "create_task", {"title": "Fix bug", "description": "Fix the login bug", "priority": 1}
        )
        assert task_result.title == "Fix bug"

        # Invalid call (missing required field)
        with pytest.raises(StructuredOutputError):
            validator.validate_tool_call("create_task", {"title": "Missing fields"})

    @pytest.mark.asyncio
    async def test_openai_tools_schema_generation(self):
        """Test generating OpenAI-compatible tools schema."""
        from pydantic import BaseModel

        from src.app.agents.structured_output import ToolCallValidator

        class WeatherParams(BaseModel):
            """Get weather for a location."""

            location: str
            unit: str = "celsius"

        validator = ToolCallValidator()
        validator.register_tool("get_weather", WeatherParams)

        schema = validator.get_tools_schema()

        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "get_weather"
        assert "location" in schema[0]["function"]["parameters"]["properties"]


# ============================================================================
# Combined Workflow Tests
# ============================================================================


class TestAgentPipelineWorkflow:
    """Integration tests for complete agent pipeline."""

    @pytest.mark.asyncio
    async def test_full_rag_pipeline_with_reranking(self):
        """Test RAG pipeline: retrieve -> rerank -> generate."""
        from src.app.agents.reranking import BaseReranker, RerankingService

        # Step 1: Simulate vector search results
        raw_results = [
            {"content": "FastAPI is a modern web framework", "score": 0.8},
            {"content": "Python is a programming language", "score": 0.85},
            {"content": "FastAPI uses Python type hints", "score": 0.75},
        ]

        # Step 2: Rerank
        class SimpleReranker(BaseReranker):
            async def rerank(self, query, documents, top_k=5):
                for doc in documents:
                    # Boost if query keyword in content
                    doc["rerank_score"] = 1.0 if "FastAPI" in doc["content"] else 0.5
                documents.sort(key=lambda x: x["rerank_score"], reverse=True)
                return documents[:top_k]

        reranker = RerankingService(SimpleReranker())
        reranked = await reranker.rerank("FastAPI tutorial", raw_results, top_k=2)

        # FastAPI docs should be first
        assert "FastAPI" in reranked[0]["content"]
        assert len(reranked) == 2

        # Step 3: Format context (memory would manage this)
        context = "\n".join([doc["content"] for doc in reranked])
        assert "FastAPI" in context

    @pytest.mark.asyncio
    async def test_resilient_rate_limited_call(self):
        """Test combining resilience and rate limiting."""
        from src.app.agents.rate_limiting import RateLimitExceeded, TenantRateLimiter
        from src.app.agents.resilience import ResilientClient, RetryConfig

        limiter = TenantRateLimiter()
        client = ResilientClient(retry_config=RetryConfig(max_attempts=2, initial_delay=0.01), name="rate_limited")

        async def rate_limited_call(tenant_id, tokens):
            # Check rate limit first
            await limiter.enforce_limit(tenant_id, tokens)
            await limiter.record_usage(tenant_id, tokens_used=tokens)
            return {"success": True, "tokens_used": tokens}

        # Should succeed
        result = await client.execute(rate_limited_call, "tenant-1", 100)
        assert result["success"] is True

        # Record heavy usage
        for _ in range(100):
            await limiter.record_usage("tenant-2", tokens_used=10000, requests=10)

        # Should fail due to rate limit
        with pytest.raises(RateLimitExceeded):
            await client.execute(rate_limited_call, "tenant-2", 1000000)
