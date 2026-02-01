"""
Tests for Entity-Aware Memory.
"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_entity_node_persistence():
    # Patch at the source
    with patch("src.app.core.config.settings") as mock_settings:
        mock_settings.ENABLE_ENTITY_MEMORY = True
        mock_settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME = "gpt-4o"
        mock_settings.AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

        # Force reload or local import to use the mock
        import src.app.agents.nodes.entity_node as entity_node

        importlib.reload(entity_node)

        mock_graph = AsyncMock()
        mock_graph.execute_query = AsyncMock(return_value=[])

        # Mock AzureChatOpenAI inside the module
        with patch("src.app.agents.nodes.entity_node.AzureChatOpenAI") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value.with_structured_output.return_value = mock_llm

            node = entity_node.EntityNode(mock_graph)

            # Mock LLM output
            mock_llm_result = MagicMock()
            mock_llm_result.entities = [
                entity_node.ExtractedEntity(name="Project Legend", label="Project", properties={"priority": "high"})
            ]
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_result)

            state = {"messages": [MagicMock(role="user", content="Tell me about Project Legend")], "tenant_id": "t1"}
            await node(state)

            # Verify merge query was called
            mock_graph.execute_query.assert_called_once()
            args, _ = mock_graph.execute_query.call_args
            assert args[1]["name"] == "project legend"


@pytest.mark.asyncio
async def test_graph_retriever_cross_thread():
    with patch("src.app.core.config.settings") as mock_settings:
        mock_settings.ENABLE_ENTITY_MEMORY = True

        import src.app.agents.graph_retriever as graph_retriever

        importlib.reload(graph_retriever)

        mock_graph = AsyncMock()
        mock_graph.execute_query = AsyncMock(
            return_value=[{"source": "project legend", "relationship": "LEADER", "target": "Manohar"}]
        )
        mock_vector = AsyncMock()
        mock_vector.similarity_search = AsyncMock(return_value=[])

        retriever = graph_retriever.GraphRetriever(mock_vector, mock_graph)
        results = await retriever.retrieve(query_text="Who is leading Project Legend?")

        assert len(results) == 1
        assert results[0]["type"] == "graph"
        assert "project legend --LEADER--> Manohar" in results[0]["content"]
