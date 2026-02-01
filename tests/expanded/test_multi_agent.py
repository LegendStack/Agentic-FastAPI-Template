from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.app.agents.supervisor import SupervisorAgent


@pytest.fixture
def mock_checkpointer():
    return InMemorySaver()


@pytest.fixture
def supervisor_agent(mock_checkpointer):
    workers = ["Researcher", "DocumentExpert"]
    return SupervisorAgent(workers=workers, checkpointer=mock_checkpointer)


@pytest.mark.asyncio
async def test_supervisor_run(supervisor_agent):
    # Mock the internal graph execution
    # Instead of running the real graph, we mock 'astream' or simply the 'invoke' if we used that
    # Since we use 'astream' in the run method, let's mock the graph.astream

    mock_stream = AsyncMock()
    mock_stream.__aiter__.return_value = [
        {"supervisor": {"next": "Researcher"}},
        {"Researcher": {"messages": [AIMessage(content="Found info")]}},
        {"supervisor": {"next": "FINISH"}},
    ]

    with patch.object(supervisor_agent.graph, "astream", return_value=mock_stream):
        # Also need to mock aget_state to return the final message
        mock_state = MagicMock()
        mock_state.values = {"messages": [AIMessage(content="Final response")]}
        supervisor_agent.graph.aget_state = AsyncMock(return_value=mock_state)

        result = await supervisor_agent.run("Tell me about LegendStack", thread_id="test_thread")

        assert isinstance(result, AIMessage)
        assert result.content == "Final response"
        supervisor_agent.graph.astream.assert_called_once()
