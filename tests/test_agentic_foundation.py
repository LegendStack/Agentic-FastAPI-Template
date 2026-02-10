"""
Comprehensive tests for the Agentic Foundation modules.
Uses mocked LLM services to ensure isolated and fast tests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --- Tests for base.py ---


class TestBaseAbstractions:
    """Tests for abstract base classes."""

    def test_agent_message_creation(self):
        from src.app.agents.base import AgentMessage

        msg = AgentMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.attachments == []

    def test_attachment_creation(self):
        from src.app.agents.base import Attachment

        att = Attachment(id="1", name="doc.pdf", content_type="application/pdf")
        assert att.id == "1"
        assert att.name == "doc.pdf"


# --- Tests for azure_openai.py ---


class TestAzureOpenAI:
    """Tests for Azure OpenAI wrapper with mocked client."""

    @patch("src.app.agents.azure_openai.settings")
    def test_get_azure_openai_chat_raises_without_config(self, mock_settings):
        mock_settings.AZURE_OPENAI_API_KEY = None
        mock_settings.AZURE_OPENAI_ENDPOINT = None
        from src.app.agents.azure_openai import get_azure_openai_chat

        with pytest.raises(ValueError, match="Azure OpenAI credentials not configured"):
            get_azure_openai_chat()

    @patch("src.app.agents.azure_openai.AzureOpenAIEmbeddings")
    @patch("src.app.agents.azure_openai.AzureChatOpenAI")
    @patch("src.app.agents.azure_openai.settings")
    def test_llm_service_get_embeddings(self, mock_settings, mock_chat, mock_embeddings):
        mock_settings.AZURE_OPENAI_AUTH_MODE = "api_key"
        mock_settings.AZURE_OPENAI_API_KEY = MagicMock()
        mock_settings.AZURE_OPENAI_API_KEY.get_secret_value.return_value = "fake-key"
        mock_settings.AZURE_OPENAI_ENDPOINT = "https://fake.openai.azure.com"
        mock_settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME = "gpt-4"
        mock_settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = "text-embedding-ada-002"
        mock_settings.AZURE_OPENAI_API_VERSION = "2023-05-15"

        mock_embeddings_instance = MagicMock()
        mock_embeddings_instance.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embeddings.return_value = mock_embeddings_instance

        from src.app.agents.azure_openai import LLMService

        service = LLMService()
        # Note: actual async test would use pytest-asyncio
        assert service.embeddings_model is not None


# --- Tests for vector_stores.py ---


class TestPgVectorStore:
    """Tests for pgvector store with mocked database."""

    @pytest.mark.asyncio
    @patch("src.app.agents.vector_stores.DocumentSection")
    async def test_add_documents(self, mock_doc_section):
        from src.app.agents.vector_stores import PgVectorStore

        mock_db = AsyncMock()
        store = PgVectorStore(mock_db)

        # Configure mock to return a mock instance when called
        mock_instance = MagicMock()
        mock_instance.id = 1
        mock_doc_section.return_value = mock_instance

        docs = [{"content": "test", "embedding": [0.1] * 1536, "source_id": "test_doc"}]

        # Mocking add_all and commit
        mock_db.add_all = MagicMock()
        mock_db.commit = AsyncMock()

        await store.add_documents(docs)
        mock_db.add_all.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_similarity_search(self):
        from src.app.agents.vector_stores import PgVectorStore

        mock_db = AsyncMock()
        store = PgVectorStore(mock_db)

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await store.similarity_search([0.1] * 1536, k=4)
        assert results == []
        mock_db.execute.assert_called_once()


# --- Tests for indexers.py ---


class TestDocumentIndexer:
    """Tests for Document Indexer with mocked dependencies."""

    @pytest.mark.asyncio
    @patch("src.app.agents.indexers.UnstructuredFileLoader")
    @patch("src.app.agents.indexers.TextLoader")
    async def test_run_indexes_file(self, mock_loader, mock_unstructured):
        from src.app.agents.indexers import DocumentIndexer

        mock_vector_store = AsyncMock()
        mock_vector_store.add_documents = AsyncMock(return_value=["id1", "id2"])

        mock_llm_service = AsyncMock()
        mock_llm_service.get_embeddings = AsyncMock(return_value=[0.1] * 1536)

        # Mock loader
        mock_doc = MagicMock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {}
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = [mock_doc]
        mock_loader.return_value = mock_loader_instance
        mock_unstructured.return_value = mock_loader_instance

        indexer = DocumentIndexer(mock_vector_store, mock_llm_service)
        result = await indexer.run(file_path="test.txt")

        assert result["status"] == "success"
        assert result["chunks_indexed"] == 2
        mock_vector_store.add_documents.assert_called_once()


# --- Tests for jira.py ---


class TestJiraIndexer:
    """Tests for Jira Indexer with mocked HTTP client."""

    @pytest.mark.asyncio
    async def test_run_indexes_issues(self):
        from src.app.agents.jira import JiraIndexer
        from src.app.services.jira_service import JiraIssue, Result

        mock_vector_store = AsyncMock()
        mock_vector_store.add_documents = AsyncMock(return_value=["id1"])

        mock_llm_service = AsyncMock()
        mock_llm_service.get_embeddings = AsyncMock(return_value=[0.1] * 1536)

        # Mock JiraService
        mock_jira_service = MagicMock()
        sample_issue = JiraIssue(
            key="TEST-1",
            summary="Test Issue",
            description="Desc",
            issue_type="Story",
            status="Open",
        )
        mock_jira_service.search_issues = AsyncMock(return_value=Result.ok([sample_issue]))

        indexer = JiraIndexer(mock_vector_store, mock_llm_service, jira_service=mock_jira_service)
        result = await indexer.run(project_key="TEST")

        assert result["status"] == "success"
        assert result["issues_indexed"] == 1
        mock_jira_service.search_issues.assert_called_once()


# --- Tests for persistence.py ---


class TestSqlAlchemyCheckpointSaver:
    """Tests for LangGraph Checkpoint Saver."""

    @pytest.mark.asyncio
    async def test_aput_stores_checkpoint(self):
        from src.app.agents.persistence import SqlAlchemyCheckpointSaver

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        saver = SqlAlchemyCheckpointSaver(mock_db)
        config = {"configurable": {"thread_id": "test-thread"}}
        checkpoint = {"id": "ckpt-1", "parent_id": None}
        metadata = {"step": 1}

        await saver.aput(config, checkpoint, metadata, {})
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
