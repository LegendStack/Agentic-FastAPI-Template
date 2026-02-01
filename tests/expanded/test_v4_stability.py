from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.agents.indexers import DocumentIndexer
from src.app.agents.reflector import Reflector
from src.app.core.config import settings


@pytest.mark.asyncio
async def test_reflector_critique():
    mock_eval_engine = MagicMock()
    mock_eval_engine.run_eval = AsyncMock(return_value=[{"faithfulness": 0.5, "answer_relevancy": 0.6}])

    mock_moderator = MagicMock()
    mock_moderator.check_safety = AsyncMock(return_value={"safe": True})
    mock_moderator.check_hallucination = AsyncMock(return_value={"is_hallucination": False})

    reflector = Reflector(eval_engine=mock_eval_engine, moderator=mock_moderator, threshold=0.8)

    result = await reflector.reflect(
        question="What is LegendStack?", response="It is a brand of soda.", contexts=["LegendStack is an AI framework."]
    )

    assert result["needs_revision"] is True
    assert "Faithfulness score is too low" in result["feedback"]
    assert "answer_relevancy" in result["scores"]


@pytest.mark.asyncio
async def test_document_indexer_unstructured_preference():
    mock_vector_store = MagicMock()
    mock_vector_store.add_documents = AsyncMock(return_value=["id1"])
    mock_llm_service = MagicMock()
    mock_llm_service.get_embeddings = AsyncMock(return_value=[0.1, 0.2])

    indexer = DocumentIndexer(vector_store=mock_vector_store, llm_service=mock_llm_service)

    # Mock UnstructuredFileLoader
    with patch("src.app.agents.indexers.UnstructuredFileLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.return_value = [MagicMock(page_content="test content", metadata={})]

        # Ensure setting is True
        with patch.object(settings, "PREFER_UNSTRUCTURED", True):
            await indexer.run("test.pdf")
            mock_loader_cls.assert_called_once_with("test.pdf")


@pytest.mark.asyncio
async def test_semantic_cache_initialization():
    # Verify that the cache can be configured
    from src.app.core.integration_config import configure_integrations

    # We patch the module-level set_llm_cache and RedisSemanticCache
    # which are now always present (possibly as None)
    with patch("src.app.core.integration_config.set_llm_cache") as mock_set_cache:
        with patch("src.app.core.encrypted_cache.EncryptedRedisSemanticCache") as mock_redis_cache:
            with patch("src.app.core.integration_config.settings") as mock_settings:
                mock_settings.ENABLE_SEMANTIC_CACHE = True
                mock_settings.REDIS_URL = "redis://localhost:6379"
                mock_settings.SEMANTIC_CACHE_THRESHOLD = 0.9
                mock_settings.SEMANTIC_CACHE_TTL = 3600

                configure_integrations()
                mock_set_cache.assert_called_once()
                mock_redis_cache.assert_called_once()
