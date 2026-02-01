"""
Tests for Phase 2 Enterprise Features.
Covers Azure AI Search, HITL, Multi-Tenant, Background Tasks, and SSE Streaming.
"""

from unittest.mock import AsyncMock, patch

import pytest

# --- Tests for Azure AI Search ---


class TestAzureAISearchStore:
    """Tests for Azure AI Search backend."""

    @pytest.mark.asyncio
    async def test_add_documents(self):
        """Test adding documents to Azure AI Search."""
        from src.app.agents.azure_search import AzureAISearchStore

        with patch("src.app.agents.azure_search.AzureAISearchStore._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.upload_documents = AsyncMock(return_value=[{"key": "doc1"}])
            mock_get_client.return_value = mock_client

            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net", api_key="test-key", index_name="test-index"
            )
            store._client = mock_client

            docs = [{"content": "test", "embedding": [0.1] * 1536}]
            ids = await store.add_documents(docs)

            assert len(ids) == 1
            mock_client.upload_documents.assert_called_once()


# --- Tests for HITL ---


class TestHITLManager:
    """Tests for Human-in-the-Loop manager."""

    @pytest.mark.asyncio
    async def test_request_approval(self):
        """Test creating an approval request."""
        from src.app.agents.hitl import HITLManager, HITLStatus

        manager = HITLManager()
        request = await manager.request_approval(
            thread_id="thread-1",
            agent_name="test_agent",
            action_type="delete",
            action_description="Delete 100 records",
            proposed_action={"count": 100},
        )

        assert request.status == HITLStatus.PENDING
        assert request.thread_id == "thread-1"
        assert "hitl_" in request.id

    @pytest.mark.asyncio
    async def test_approve_request(self):
        """Test approving an HITL request."""
        from src.app.agents.hitl import HITLManager, HITLStatus

        manager = HITLManager()
        request = await manager.request_approval(
            thread_id="thread-1",
            agent_name="test_agent",
            action_type="delete",
            action_description="Delete records",
            proposed_action={},
        )

        approved = await manager.approve(request.id, "admin", "Looks good")
        assert approved.status == HITLStatus.APPROVED
        assert approved.reviewed_by == "admin"

    @pytest.mark.asyncio
    async def test_reject_request(self):
        """Test rejecting an HITL request."""
        from src.app.agents.hitl import HITLManager, HITLStatus

        manager = HITLManager()
        request = await manager.request_approval(
            thread_id="thread-1",
            agent_name="test_agent",
            action_type="delete",
            action_description="Delete records",
            proposed_action={},
        )

        rejected = await manager.reject(request.id, "admin", "Too risky")
        assert rejected.status == HITLStatus.REJECTED
        assert rejected.reviewer_notes == "Too risky"


# --- Tests for Multi-Tenant ---


class TestMultiTenant:
    """Tests for multi-tenant isolation."""

    def test_tenant_context_sets_tenant(self):
        """Test that tenant context properly sets the current tenant."""
        from src.app.agents.multi_tenant import TenantManager

        manager = TenantManager()

        assert manager.get_current_tenant() is None

        with manager.tenant_context("tenant-123"):
            assert manager.get_current_tenant() == "tenant-123"
            assert manager.get_filters() == {"tenant_id": "tenant-123"}

        assert manager.get_current_tenant() is None

    @pytest.mark.asyncio
    async def test_multi_tenant_vector_store(self):
        """Test that multi-tenant wrapper adds tenant_id to documents."""
        from src.app.agents.multi_tenant import MultiTenantVectorStore, TenantManager

        manager = TenantManager()
        mock_base_store = AsyncMock()
        mock_base_store.add_documents = AsyncMock(return_value=["id1"])

        mt_store = MultiTenantVectorStore(mock_base_store, manager)

        with manager.tenant_context("tenant-abc"):
            docs = [{"content": "test", "embedding": [0.1] * 1536}]
            await mt_store.add_documents(docs)

            # Verify tenant_id was injected
            call_args = mock_base_store.add_documents.call_args
            assert call_args[0][0][0]["tenant_id"] == "tenant-abc"


# --- Tests for SSE Streaming ---


class TestSSEStreaming:
    """Tests for SSE streaming utilities."""

    @pytest.mark.asyncio
    async def test_streaming_chat_response(self):
        """Test the streaming response helper."""
        from src.app.agents.streaming import StreamingChatResponse

        response = StreamingChatResponse()

        async def mock_tokens():
            yield "Hello"
            yield " World"

        events = []
        async for event in response.stream_tokens(mock_tokens()):
            events.append(event)

        assert len(events) == 3  # 2 tokens + 1 done event
        assert events[0] == {"type": "token", "content": "Hello"}
        assert events[1] == {"type": "token", "content": " World"}
        assert events[2]["type"] == "done"
        assert events[2]["content"] == "Hello World"
