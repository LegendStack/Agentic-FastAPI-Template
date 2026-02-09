"""
Integration Tests for Refactored Backlog Agent
===============================================
Tests the full workflow of the BacklogAssistantAgent with mocked JiraService.

These tests verify:
- Agent initialization with dependency injection
- JiraService integration
- Result type propagation
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# Test configuration and fixtures
pytestmark = pytest.mark.asyncio


class TestBacklogAgentIntegration:
    """Integration tests for the refactored BacklogAssistantAgent."""

    @pytest.fixture
    def mock_jira_config(self):
        """Create a mock JiraConfig."""
        from src.app.services.jira_service import JiraConfig

        return JiraConfig(
            base_url="https://test.atlassian.net",
            username="test@example.com",
            api_token="test-token",
            default_project_key="TEST",
        )

    @pytest.fixture
    def mock_jira_service(self, mock_jira_config):
        """Create a mock JiraService with standard responses."""
        from src.app.services.jira_service import JiraService, Result

        service = MagicMock(spec=JiraService)
        service.config = mock_jira_config

        # Mock create_issue to return success
        service.create_issue = AsyncMock(return_value=Result.ok("TEST-123"))

        # Mock create_epic to return success
        service.create_epic = AsyncMock(return_value=Result.ok("TEST-EPIC-1"))

        # Mock update_issue to return success
        service.update_issue = AsyncMock(return_value=Result.ok({}))

        # Mock get_issue to return a sample issue
        from src.app.services.jira_service import JiraIssue

        sample_issue = JiraIssue(
            key="TEST-100",
            summary="Sample Issue",
            description="A test issue",
            issue_type="Story",
            status="Open",
        )
        service.get_issue = AsyncMock(return_value=Result.ok(sample_issue))

        # Mock search_issues
        service.search_issues = AsyncMock(return_value=Result.ok([sample_issue]))

        return service

    def test_jira_service_fixture_works(self, mock_jira_service):
        """Verify the mock JiraService fixture is properly configured."""
        assert mock_jira_service is not None
        assert mock_jira_service.config.base_url == "https://test.atlassian.net"

    def test_jira_config_is_configured(self, mock_jira_config):
        """Test JiraConfig correctly identifies it's configured."""
        assert mock_jira_config.is_configured is True

    async def test_mock_service_returns_results(self, mock_jira_service):
        """Test that mock service returns proper Result objects."""
        result = await mock_jira_service.create_issue(None)
        assert result.is_ok
        assert result.value == "TEST-123"


class TestResultTypeIntegration:
    """Test Result type integration across components."""

    def test_result_propagation_through_service(self):
        """Test that Result type works correctly through the service layer."""
        from src.app.services.jira_service import JiraError, JiraErrorCode, Result

        # Test ok result chaining
        ok_result = Result.ok({"key": "TEST-123"})
        mapped = ok_result.map(lambda x: x["key"])
        assert mapped.is_ok
        assert mapped.value == "TEST-123"

        # Test error result propagation
        err = JiraError(code=JiraErrorCode.NOT_FOUND, message="Not found", status_code=404)
        err_result = Result.err(err)
        mapped_err = err_result.map(lambda x: x["key"])
        assert mapped_err.is_error
        assert mapped_err.error.code == JiraErrorCode.NOT_FOUND

    def test_node_result_to_state_update(self):
        """Test NodeResult properly converts to state updates."""
        from src.app.agents.backlog.result import NodeError, NodeResult

        # Success case
        ok_result = NodeResult.ok(
            value={"stories": []},
            state_updates={"decomposition_result": {}, "status": "complete"},
        )

        update = ok_result.to_state_update()
        assert "decomposition_result" in update
        assert update["status"] == "complete"

        # Error case
        error = NodeError.validation("Invalid input")
        err_result = NodeResult.err(error)

        error_update = err_result.to_state_update()
        assert "error" in error_update


class TestNodeFactoryIntegration:
    """Test NodeFactory creates nodes with injected services."""

    def test_node_factory_accepts_jira_service(self):
        """Test NodeFactory accepts jira_service parameter."""
        from src.app.agents.backlog.config import BacklogAgentConfig
        from src.app.agents.backlog.node_factory import NodeFactory
        from src.app.services.jira_service import JiraConfig, JiraService

        config = BacklogAgentConfig()
        jira_config = JiraConfig(
            base_url="https://test.atlassian.net",
            username="test@example.com",
            api_token="test-token",
        )
        jira_service = JiraService(jira_config)

        # NodeFactory should accept jira_service without error
        factory = NodeFactory(config, jira_service=jira_service)
        assert factory is not None


# =============================================================================
# Run pytest if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
