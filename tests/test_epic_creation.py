import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.app.agents.backlog.nodes.export_node import ExportNode
from src.app.agents.backlog.schemas import DecompositionResult, Epic, UserStory, AcceptanceCriteria
from src.app.agents.backlog.config import BacklogAgentConfig

@pytest.mark.asyncio
async def test_auto_epic_creation():
    # Setup mock config and node
    config = BacklogAgentConfig(ENABLE_JIRA_EXPORT=True, JIRA_EPIC_LINK_FIELD="customfield_10014", JIRA_EPIC_NAME_FIELD="customfield_10011")
    node = ExportNode(config=config)
    
    # Mock data
    epic = Epic(title="New Test Epic", description="Description for new epic")
    stories = [
        UserStory(id="S1", title="Story 1", description="Desc 1", acceptance_criteria=[AcceptanceCriteria(description="AC1")]),
    ]
    result = DecompositionResult(epic=epic, stories=stories, summary="Summary")
    state = {"parent_epic_id": None}
    
    # Mock Jira responses
    mock_epic_response = MagicMock()
    mock_epic_response.json.return_value = {"key": "NEW-EPIC-123"}
    mock_epic_response.status_code = 201
    
    mock_story_response = MagicMock()
    mock_story_response.json.return_value = {"key": "STORY-456"}
    mock_story_response.status_code = 201
    
    with patch("httpx.AsyncClient.post") as mock_post:
        # First call: Epic creation, Second call: Story creation
        mock_post.side_effect = [mock_epic_response, mock_story_response]
        
        # Run export
        export_result = await node._jira_export(result, state)
        
        # Verify Epic creation call
        epic_call = mock_post.call_args_list[0]
        epic_payload = epic_call.kwargs["json"]
        assert epic_payload["fields"]["issuetype"]["name"] == "Epic"
        assert epic_payload["fields"]["summary"] == "New Test Epic"
        assert epic_payload["fields"]["customfield_10011"] == "New Test Epic"
        
        # Verify Story creation call (linking)
        story_call = mock_post.call_args_list[1]
        story_payload = story_call.kwargs["json"]
        assert story_payload["fields"]["customfield_10014"] == "NEW-EPIC-123"
        
        # Verify result
        assert export_result["status"] == "success"
        assert len(export_result["issues"]) == 2  # Epic + Story
        assert export_result["issues"][0]["jira_key"] == "NEW-EPIC-123"
        assert export_result["issues"][1]["jira_key"] == "STORY-456"

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_auto_epic_creation())
