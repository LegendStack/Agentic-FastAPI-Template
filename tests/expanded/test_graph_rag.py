from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.agents.graph_retriever import GraphRetriever


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.similarity_search = AsyncMock()
    return store


@pytest.fixture
def mock_graph_client():
    client = MagicMock()
    client.execute_query = AsyncMock()
    return client


@pytest.fixture
def graph_retriever(mock_vector_store, mock_graph_client):
    return GraphRetriever(vector_store=mock_vector_store, graph_client=mock_graph_client)


@pytest.mark.asyncio
async def test_graph_retriever_retrieve(graph_retriever, mock_vector_store, mock_graph_client):
    # Mock vector results
    mock_vector_store.similarity_search.return_value = [
        {"content": "FastAPI is great", "source_id": "fastapi_1", "metadata": {}},
        {"content": "Python is powerful", "source_id": "python_1", "metadata": {}},
    ]

    # Mock graph results
    mock_graph_client.execute_query.return_value = [
        {"source": "FastAPI", "relationship": "WRITTEN_IN", "target": "Python"}
    ]

    query_vector = [0.1] * 1536
    from src.app.core import config
    with patch.object(config.settings, "ENABLE_ENTITY_MEMORY", True):
        results = await graph_retriever.retrieve(query_text="test query", query_vector=query_vector, k=2)

    assert len(results) == 3  # 2 vector + 1 graph triplet block
    assert results[0]["type"] == "vector"
    assert results[2]["type"] == "graph"
    assert "WRITTEN_IN" in results[2]["content"]

    mock_vector_store.similarity_search.assert_called_once()
    mock_graph_client.execute_query.assert_called_once()
