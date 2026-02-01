"""
Unit Tests for Phase 6 Advanced Enhancements.
==============================================
Tests for Memory, Reranking, Structured Output, Resilience, Rate Limiting,
WebSocket, Prompts modules.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

# ============================================================================
# Memory Management Tests
# ============================================================================


class TestTruncationStrategy:
    """Tests for TruncationStrategy context management."""

    @pytest.fixture
    def mock_conversation_service(self):
        service = MagicMock()
        return service

    @pytest.fixture
    def truncation_strategy(self, mock_conversation_service):
        from src.app.agents.memory import TruncationStrategy

        return TruncationStrategy(mock_conversation_service)

    def test_count_tokens(self, truncation_strategy):
        """Test token counting."""
        text = "Hello, world!"
        count = truncation_strategy.count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty(self, truncation_strategy):
        """Test token counting for empty string."""
        count = truncation_strategy.count_tokens("")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_context_simple(self, truncation_strategy, mock_conversation_service):
        """Test getting context with simple messages."""
        # Mock messages
        mock_msg1 = MagicMock(role="user", content="Hello")
        mock_msg2 = MagicMock(role="assistant", content="Hi there!")
        mock_conversation_service.get_messages = AsyncMock(return_value=[mock_msg1, mock_msg2])

        context = await truncation_strategy.get_context("thread-123", max_tokens=1000)

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"


class TestMemoryManager:
    """Tests for MemoryManager."""

    @pytest.fixture
    def mock_services(self):
        conv_service = MagicMock()
        llm_service = MagicMock()
        return conv_service, llm_service

    @pytest.fixture
    def memory_manager(self, mock_services):
        from src.app.agents.memory import MemoryManager

        conv_service, llm_service = mock_services
        return MemoryManager(conv_service, llm_service)

    def test_default_max_tokens(self, memory_manager):
        """Test default max tokens is set."""
        assert memory_manager.default_max_tokens == 4000

    def test_set_strategy(self, memory_manager, mock_services):
        """Test changing memory strategy."""
        from src.app.agents.memory import SummarizationStrategy

        conv_service, llm_service = mock_services

        new_strategy = SummarizationStrategy(conv_service, llm_service)
        memory_manager.set_strategy(new_strategy)

        assert memory_manager._strategy == new_strategy


# ============================================================================
# Reranking Tests
# ============================================================================


class TestRerankingService:
    """Tests for RerankingService."""

    @pytest.fixture
    def reranking_service(self):
        from src.app.agents.reranking import RerankingService

        return RerankingService()

    @pytest.mark.asyncio
    async def test_rerank_no_reranker(self, reranking_service):
        """Test reranking without a reranker returns docs as-is."""
        docs = [
            {"content": "Doc 1", "score": 0.9},
            {"content": "Doc 2", "score": 0.8},
            {"content": "Doc 3", "score": 0.7},
        ]

        result = await reranking_service.rerank("query", docs, top_k=2)

        assert len(result) == 2
        assert result[0]["content"] == "Doc 1"

    @pytest.mark.asyncio
    async def test_rerank_empty_docs(self, reranking_service):
        """Test reranking with empty documents."""
        result = await reranking_service.rerank("query", [], top_k=5)
        assert result == []

    def test_set_reranker(self, reranking_service):
        """Test setting a custom reranker."""
        from src.app.agents.reranking import BaseReranker

        mock_reranker = MagicMock(spec=BaseReranker)
        reranking_service.set_reranker(mock_reranker)

        assert reranking_service._reranker == mock_reranker


class TestBaseReranker:
    """Tests for BaseReranker implementations."""

    def test_cross_encoder_reranker_init(self):
        """Test CrossEncoderReranker initialization."""
        from src.app.agents.reranking import CrossEncoderReranker

        reranker = CrossEncoderReranker(model_name="test-model")
        assert reranker.model_name == "test-model"
        assert reranker._model is None  # Lazy loading


# ============================================================================
# Structured Output Tests
# ============================================================================


class TestStructuredOutputValidator:
    """Tests for StructuredOutputValidator."""

    @pytest.fixture
    def validator(self):
        from src.app.agents.structured_output import StructuredOutputValidator

        return StructuredOutputValidator()

    def test_validate_valid_json(self, validator):
        """Test validation with valid JSON."""

        class TestModel(BaseModel):
            name: str
            value: int

        result = validator.validate('{"name": "test", "value": 42}', TestModel)

        assert result.name == "test"
        assert result.value == 42

    def test_validate_invalid_json(self, validator):
        """Test validation with invalid JSON raises error."""
        from src.app.agents.structured_output import StructuredOutputError

        class TestModel(BaseModel):
            name: str

        with pytest.raises(StructuredOutputError):
            validator.validate("not valid json", TestModel)

    def test_validate_missing_field(self, validator):
        """Test validation with missing required field."""
        from src.app.agents.structured_output import StructuredOutputError

        class TestModel(BaseModel):
            name: str
            required_field: int

        with pytest.raises(StructuredOutputError):
            validator.validate('{"name": "test"}', TestModel)

    def test_extract_json_from_markdown(self, validator):
        """Test extracting JSON from markdown code blocks."""
        content = """Here is the response:
```json
{"name": "test", "value": 123}
```
"""
        result = validator._extract_json(content)
        assert result["name"] == "test"
        assert result["value"] == 123


class TestToolCallValidator:
    """Tests for ToolCallValidator."""

    @pytest.fixture
    def tool_validator(self):
        from src.app.agents.structured_output import ToolCallValidator

        return ToolCallValidator()

    def test_register_tool(self, tool_validator):
        """Test registering a tool."""

        class SearchParams(BaseModel):
            query: str
            limit: int = 10

        tool_validator.register_tool("search", SearchParams)

        assert "search" in tool_validator.list_tools()

    def test_validate_tool_call(self, tool_validator):
        """Test validating a tool call."""

        class SearchParams(BaseModel):
            query: str

        tool_validator.register_tool("search", SearchParams)
        result = tool_validator.validate_tool_call("search", {"query": "hello"})

        assert result.query == "hello"

    def test_validate_unknown_tool(self, tool_validator):
        """Test validating unknown tool raises error."""
        from src.app.agents.structured_output import StructuredOutputError

        with pytest.raises(StructuredOutputError, match="Unknown tool"):
            tool_validator.validate_tool_call("unknown", {})

    def test_get_tools_schema(self, tool_validator):
        """Test getting OpenAI-compatible tools schema."""

        class SearchParams(BaseModel):
            """Search for documents."""

            query: str

        tool_validator.register_tool("search", SearchParams)
        schema = tool_validator.get_tools_schema()

        assert len(schema) == 1
        assert schema[0]["type"] == "function"
        assert schema[0]["function"]["name"] == "search"


# ============================================================================
# Resilience Tests
# ============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def circuit_breaker(self):
        from src.app.agents.resilience import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=1)
        return CircuitBreaker(config, name="test")

    def test_initial_state_closed(self, circuit_breaker):
        """Test circuit starts in closed state."""
        from src.app.agents.resilience import CircuitState

        assert circuit_breaker.state == CircuitState.CLOSED

    def test_opens_after_failures(self, circuit_breaker):
        """Test circuit opens after threshold failures."""
        from src.app.agents.resilience import CircuitState

        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

    def test_success_resets_failure_count(self, circuit_breaker):
        """Test success resets failure count."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()

        assert circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_context_manager_success(self, circuit_breaker):
        """Test circuit breaker as async context manager on success."""
        async with circuit_breaker:
            pass  # Success

        assert circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_context_manager_failure(self, circuit_breaker):
        """Test circuit breaker as async context manager on failure."""
        with pytest.raises(ValueError):
            async with circuit_breaker:
                raise ValueError("Test error")

        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_reject_when_open(self, circuit_breaker):
        """Test circuit rejects calls when open."""
        from src.app.agents.resilience import CircuitOpenError

        # Open the circuit
        for _ in range(3):
            circuit_breaker.record_failure()

        with pytest.raises(CircuitOpenError):
            async with circuit_breaker:
                pass


class TestRetryWithBackoff:
    """Tests for retry_with_backoff."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test successful call on first attempt."""
        from src.app.agents.resilience import retry_with_backoff

        async def success_fn():
            return "success"

        result = await retry_with_backoff(success_fn)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test successful retry after initial failures."""
        from src.app.agents.resilience import RetryConfig, retry_with_backoff

        attempts = [0]

        async def flaky_fn():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("Temporary failure")
            return "success"

        config = RetryConfig(max_attempts=5, initial_delay=0.01)
        result = await retry_with_backoff(flaky_fn, config)

        assert result == "success"
        assert attempts[0] == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry exhaustion raises last exception."""
        from src.app.agents.resilience import RetryConfig, retry_with_backoff

        async def always_fails():
            raise ValueError("Always fails")

        config = RetryConfig(max_attempts=2, initial_delay=0.01)

        with pytest.raises(ValueError, match="Always fails"):
            await retry_with_backoff(always_fails, config)


class TestResilientClient:
    """Tests for ResilientClient."""

    @pytest.fixture
    def resilient_client(self):
        from src.app.agents.resilience import CircuitBreakerConfig, ResilientClient, RetryConfig

        return ResilientClient(
            retry_config=RetryConfig(max_attempts=2, initial_delay=0.01),
            circuit_config=CircuitBreakerConfig(failure_threshold=3),
            name="test",
        )

    @pytest.mark.asyncio
    async def test_execute_success(self, resilient_client):
        """Test successful execution."""

        async def success_fn():
            return "result"

        result = await resilient_client.execute(success_fn)
        assert result == "result"

    def test_reset(self, resilient_client):
        """Test resetting the circuit breaker."""
        from src.app.agents.resilience import CircuitState

        # Cause failures
        for _ in range(3):
            resilient_client.breaker.record_failure()

        assert resilient_client.circuit_state == CircuitState.OPEN

        resilient_client.reset()
        assert resilient_client.circuit_state == CircuitState.CLOSED


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter."""

    @pytest.fixture
    def rate_limiter(self):
        from src.app.agents.rate_limiting import InMemoryRateLimiter, RateLimitConfig

        config = RateLimitConfig(tokens_per_minute=100, requests_per_minute=10)
        return InMemoryRateLimiter(default_config=config)

    @pytest.mark.asyncio
    async def test_check_limit_allowed(self, rate_limiter):
        """Test request is allowed when under limit."""
        result = await rate_limiter.check_limit("tenant-1", tokens_requested=50)
        assert result is True

    @pytest.mark.asyncio
    async def test_record_and_check_usage(self, rate_limiter):
        """Test recording usage and checking limits."""
        await rate_limiter.record_usage("tenant-1", tokens_used=80, requests=1)

        # Should still be allowed for 20 more tokens
        result = await rate_limiter.check_limit("tenant-1", tokens_requested=20)
        assert result is True

        # Should be denied for 21 more tokens (would exceed 100)
        result = await rate_limiter.check_limit("tenant-1", tokens_requested=21)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_usage(self, rate_limiter):
        """Test getting usage statistics."""
        await rate_limiter.record_usage("tenant-1", tokens_used=50, requests=5)

        usage = await rate_limiter.get_usage("tenant-1")

        assert usage.tenant_id == "tenant-1"
        assert usage.tokens_used == 50
        assert usage.requests_made == 5
        # tokens_limit is the hourly limit, not minute limit
        assert usage.tokens_limit > 0

    def test_set_tenant_tier(self, rate_limiter):
        """Test setting tenant tier."""
        from src.app.agents.rate_limiting import RATE_LIMIT_TIERS

        rate_limiter.set_tenant_tier("tenant-1", "premium")

        config = rate_limiter._get_config("tenant-1")
        assert config == RATE_LIMIT_TIERS["premium"]


class TestTenantRateLimiter:
    """Tests for TenantRateLimiter."""

    @pytest.fixture
    def tenant_limiter(self):
        from src.app.agents.rate_limiting import TenantRateLimiter

        return TenantRateLimiter()

    @pytest.mark.asyncio
    async def test_enforce_limit_allowed(self, tenant_limiter):
        """Test enforce_limit passes when allowed."""
        await tenant_limiter.enforce_limit("tenant-1", tokens_requested=10)
        # Should not raise

    @pytest.mark.asyncio
    async def test_enforce_limit_exceeded(self, tenant_limiter):
        """Test enforce_limit raises when exceeded."""
        from src.app.agents.rate_limiting import RateLimitExceeded

        # Record heavy usage
        for _ in range(200):
            await tenant_limiter.record_usage("tenant-1", tokens_used=1000, requests=1)

        with pytest.raises(RateLimitExceeded):
            await tenant_limiter.enforce_limit("tenant-1", tokens_requested=1000000)


# ============================================================================
# Prompt Versioning Tests
# ============================================================================


class TestPromptRegistry:
    """Tests for PromptRegistry."""

    @pytest.fixture
    def prompt_registry(self):
        from src.app.agents.prompts import PromptRegistry

        return PromptRegistry()

    @pytest.mark.asyncio
    async def test_set_prompt(self, prompt_registry):
        """Test setting a new prompt."""
        version = await prompt_registry.set("test_prompt", "You are a helpful assistant.", created_by="test")

        assert version.name == "test_prompt"
        assert version.version == 1
        assert version.content == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_get_prompt(self, prompt_registry):
        """Test getting a prompt."""
        await prompt_registry.set("test_prompt", "Test content")

        content = await prompt_registry.get("test_prompt")
        assert content == "Test content"

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(self, prompt_registry):
        """Test getting non-existent prompt returns default."""
        content = await prompt_registry.get("nonexistent", default="fallback")
        assert content == "fallback"

    @pytest.mark.asyncio
    async def test_version_increment(self, prompt_registry):
        """Test version increments on content change."""
        await prompt_registry.set("test", "v1 content")
        await prompt_registry.set("test", "v2 content")

        versions = await prompt_registry.list_versions("test")
        assert len(versions) == 2
        assert versions[0].version == 2  # Newest first

    @pytest.mark.asyncio
    async def test_no_version_bump_if_unchanged(self, prompt_registry):
        """Test no version bump if content unchanged."""
        await prompt_registry.set("test", "same content")
        await prompt_registry.set("test", "same content")

        versions = await prompt_registry.list_versions("test")
        assert len(versions) == 1

    @pytest.mark.asyncio
    async def test_rollback(self, prompt_registry):
        """Test rolling back to previous version."""
        await prompt_registry.set("test", "v1 content")
        await prompt_registry.set("test", "v2 content")

        await prompt_registry.rollback("test", version=1)

        content = await prompt_registry.get("test")
        assert content == "v1 content"

    @pytest.mark.asyncio
    async def test_get_specific_version(self, prompt_registry):
        """Test getting a specific version."""
        await prompt_registry.set("test", "v1 content")
        await prompt_registry.set("test", "v2 content")

        content = await prompt_registry.get("test", version=1)
        assert content == "v1 content"


# ============================================================================
# WebSocket Tests
# ============================================================================


class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    @pytest.fixture
    def connection_manager(self):
        from src.app.agents.websocket import ConnectionManager

        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect(self, connection_manager):
        """Test connecting a websocket."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        conn = await connection_manager.connect(mock_ws, "thread-1", "user-1")

        mock_ws.accept.assert_called_once()
        assert conn.thread_id == "thread-1"
        assert conn.user_id == "user-1"
        assert "thread-1" in connection_manager.list_connections()

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager):
        """Test disconnecting a websocket."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await connection_manager.connect(mock_ws, "thread-1")
        await connection_manager.disconnect("thread-1")

        assert "thread-1" not in connection_manager.list_connections()

    @pytest.mark.asyncio
    async def test_send_token(self, connection_manager):
        """Test sending a token."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        await connection_manager.connect(mock_ws, "thread-1")
        result = await connection_manager.send_token("thread-1", "Hello")

        assert result is True
        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_nonexistent(self, connection_manager):
        """Test sending to non-existent connection returns False."""
        from src.app.agents.websocket import WSMessage, WSMessageType

        result = await connection_manager.send(
            "nonexistent", WSMessage(type=WSMessageType.TOKEN, data={"token": "test"})
        )

        assert result is False


class TestWSMessage:
    """Tests for WSMessage."""

    def test_message_creation(self):
        """Test creating a WebSocket message."""
        from src.app.agents.websocket import WSMessage, WSMessageType

        msg = WSMessage(type=WSMessageType.TOKEN, data={"token": "hello"})

        assert msg.type == WSMessageType.TOKEN
        assert msg.data["token"] == "hello"
        assert msg.timestamp is not None
