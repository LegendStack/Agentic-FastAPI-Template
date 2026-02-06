import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.app.agents.backlog.backlog_agent import BacklogAssistantAgent
from src.app.agents.backlog.schemas import UserStory, DecompositionResult, Epic

async def test_message_formatting():
    # 1. Setup Agent and Mock Service
    agent = BacklogAssistantAgent()
    agent.checkpointer = MagicMock()
    agent.checkpointer.db = MagicMock()
    
    # Mock ConversationService
    mock_conv_service = AsyncMock()
    import src.app.agents.backlog.conversations as conversations
    conversations.ConversationService = MagicMock(return_value=mock_conv_service)

    # 2. Mock State and Save Result (New Epic Case)
    thread_id = "test-thread-new"
    state = {
        "thread_id": thread_id,
        "parsed_epic": Epic(title="Mars Mission Project", description="Decompose Mars"),
        "stories": [],
        "project_key": "KAN",
        "parent_epic_id": None
    }
    
    # Simulate ExportNode result for NEW epic
    save_result = {
        "status": "success",
        "export_result": {
            "status": "success",
            "epic_key": "KAN-1",
            "issues": [
                {"internal_id": "EPIC", "jira_key": "KAN-1", "url": "url-epic", "summary": "Mars Mission Project"},
                {"internal_id": "s1", "jira_key": "KAN-2", "url": "url-s1", "summary": "Story 1"},
                {"internal_id": "s2", "jira_key": "KAN-3", "url": "url-s2", "summary": "Story 2"},
            ]
        },
        "stories": [UserStory(id="s1", title="Story 1"), UserStory(id="s2", title="Story 2")],
    }
    
    # Mock save_node and graph state
    agent.save_node = AsyncMock(return_value=save_result)
    agent.graph = MagicMock()
    agent.graph.aget_state = AsyncMock(return_value=MagicMock(values=state))
    agent.graph.aupdate_state = AsyncMock()

    print("--- Testing New Epic Message ---")
    await agent.save_to_jira(thread_id)
    
    call_args = mock_conv_service.add_message.call_args_list[-1]
    content = call_args.kwargs['content']
    print(f"Message content:\n{content}")
    assert "Epic Created/Linked:" in content
    assert "[KAN-1](url-epic) - Mars Mission Project" in content
    assert "[KAN-2](url-s1) - Story 1" in content
    print("[PASS] New Epic message formatting looks good.")

    # 3. Mock State and Save Result (Pre-existing Epic Case)
    thread_id_ext = "test-thread-ext"
    mock_conv_service.add_message.reset_mock()
    state_ext = {
        "thread_id": thread_id_ext,
        "parsed_epic": Epic(title="Existing Home Repair", description="Fix pipes"),
        "stories": [],
        "project_key": "KAN",
        "parent_epic_id": "KAN-99"
    }
    
    save_result_ext = {
        "status": "success",
        "export_result": {
            "status": "success",
            "epic_key": "KAN-99",
            "issues": [
                {"internal_id": "s1", "jira_key": "KAN-100", "url": "url-s100", "summary": "Fix Pipe A"},
            ]
        },
        "stories": [UserStory(id="s1", title="Fix Pipe A")],
    }
    
    agent.graph.aget_state = AsyncMock(return_value=MagicMock(values=state_ext))
    agent.save_node = AsyncMock(return_value=save_result_ext)

    print("\n--- Testing Pre-existing Epic Message ---")
    await agent.save_to_jira(thread_id_ext)
    
    call_args = mock_conv_service.add_message.call_args_list[-1]
    content = call_args.kwargs['content']
    print(f"Message content:\n{content}")
    assert "Linked to Parent Epic:" in content
    assert "[KAN-99]" in content
    assert "Existing Home Repair" in content # Summary from state
    print("[PASS] Pre-existing Epic message formatting looks good.")

if __name__ == "__main__":
    asyncio.run(test_message_formatting())
