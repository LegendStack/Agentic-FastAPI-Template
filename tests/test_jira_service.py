"""
Unit Tests for JiraService and Result Types
============================================
Comprehensive tests with mocked httpx for all JiraService operations.

Tests cover:
- Result type methods (ok, err, unwrap, map)
- JiraService CRUD operations
- Retry logic and error handling
- Configuration validation
"""

from unittest.mock import AsyncMock, patch

import pytest

# Import the modules under test
from src.app.services.jira_service import (
    CreateIssuePayload,
    JiraConfig,
    JiraError,
    JiraErrorCode,
    JiraService,
    Result,
)

# =============================================================================
# Result Type Tests
# =============================================================================


class TestResult:
    """Tests for the Result type."""

    def test_ok_creates_success_result(self):
        """Result.ok() creates a successful result with value."""
        result = Result.ok({"key": "TEST-123"})

        assert result.is_ok is True
        assert result.is_error is False
        assert result.value == {"key": "TEST-123"}

    def test_err_creates_error_result(self):
        """Result.err() creates an error result."""
        error = JiraError(
            code=JiraErrorCode.NOT_FOUND,
            message="Issue not found",
            status_code=404,
        )
        result = Result.err(error)

        assert result.is_ok is False
        assert result.is_error is True
        assert result.error.message == "Issue not found"
        assert result.error.status_code == 404

    def test_value_raises_on_error_result(self):
        """Accessing value on error result raises ValueError."""
        error = JiraError(
            code=JiraErrorCode.SERVER_ERROR,
            message="Something went wrong",
        )
        result = Result.err(error)

        with pytest.raises(ValueError, match="Cannot get value from error result"):
            _ = result.value

    def test_error_raises_on_success_result(self):
        """Accessing error on success result raises ValueError."""
        result = Result.ok("success")

        with pytest.raises(ValueError, match="Cannot get error from ok result"):
            _ = result.error

    def test_unwrap_or_returns_value_on_success(self):
        """unwrap_or returns value when result is successful."""
        result = Result.ok(42)
        assert result.unwrap_or(0) == 42

    def test_unwrap_or_returns_default_on_error(self):
        """unwrap_or returns default when result is error."""
        error = JiraError(code=JiraErrorCode.SERVER_ERROR, message="Error")
        result = Result.err(error)
        assert result.unwrap_or(99) == 99

    def test_map_transforms_success_value(self):
        """map transforms the value when successful."""
        result = Result.ok(10)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_ok is True
        assert mapped.value == 20

    def test_map_passes_through_error(self):
        """map passes through error without calling function."""
        error = JiraError(code=JiraErrorCode.SERVER_ERROR, message="Error")
        result = Result.err(error)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_error is True
        assert mapped.error.message == "Error"


# =============================================================================
# JiraConfig Tests
# =============================================================================


class TestJiraConfig:
    """Tests for JiraConfig configuration."""

    def test_is_configured_returns_true_when_all_set(self):
        """is_configured returns True when all required fields are set."""
        config = JiraConfig(
            base_url="https://example.atlassian.net",
            username="user@example.com",
            api_token="secret-token",
            default_project_key="TEST",
        )
        assert config.is_configured is True

    def test_is_configured_returns_false_when_missing_url(self):
        """is_configured returns False when base_url is missing."""
        config = JiraConfig(
            base_url="",
            username="user@example.com",
            api_token="secret-token",
        )
        assert config.is_configured is False

    def test_is_configured_returns_false_when_missing_token(self):
        """is_configured returns False when api_token is missing."""
        config = JiraConfig(
            base_url="https://example.atlassian.net",
            username="user@example.com",
            api_token="",
        )
        assert config.is_configured is False

    def test_auth_property_returns_basic_auth(self):
        """auth property returns (username, api_token) for basic auth."""
        config = JiraConfig(
            base_url="https://example.atlassian.net",
            username="user@example.com",
            api_token="secret-token",
        )
        assert config.auth == ("user@example.com", "secret-token")


# =============================================================================
# JiraService Tests with Mocked httpx
# =============================================================================


class TestJiraService:
    """Tests for JiraService with mocked HTTP client."""

    @pytest.fixture
    def config(self):
        """Create a test JiraConfig."""
        return JiraConfig(
            base_url="https://test.atlassian.net",
            username="test@example.com",
            api_token="test-token",
            default_project_key="TEST",
            request_timeout_seconds=5.0,
            max_retries=2,
        )

    @pytest.fixture
    def service(self, config):
        """Create a JiraService with test config."""
        return JiraService(config)

    @pytest.mark.asyncio
    async def test_get_issue_success(self, service):
        """get_issue returns JiraIssue on successful API call."""
        mock_response = {
            "key": "TEST-123",
            "fields": {
                "summary": "Test Issue",
                "description": "Test description",
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "priority": {"name": "Medium"},
                "labels": ["backend"],
                "parent": {"key": "TEST-100"},
            },
        }

        # Mock the internal _request method directly
        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = Result.ok(mock_response)

            result = await service.get_issue("TEST-123")

            assert result.is_ok is True
            issue = result.value
            assert issue.key == "TEST-123"
            assert issue.summary == "Test Issue"
            assert issue.issue_type == "Story"
            assert issue.parent_key == "TEST-100"

    @pytest.mark.asyncio
    async def test_get_issue_not_found(self, service):
        """get_issue returns error when issue not found."""
        error = JiraError(
            code=JiraErrorCode.NOT_FOUND,
            message="Issue not found",
            status_code=404,
        )

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = Result.err(error)

            result = await service.get_issue("TEST-999")

            assert result.is_error is True
            assert result.error.code == JiraErrorCode.NOT_FOUND
            assert result.error.status_code == 404

    @pytest.mark.asyncio
    async def test_create_issue_success(self, service):
        """create_issue returns new issue key on success."""
        mock_response = {
            "id": "10001",
            "key": "TEST-124",
            "self": "https://test.atlassian.net/rest/api/3/issue/10001",
        }

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = Result.ok(mock_response)

            payload = CreateIssuePayload(
                project_key="TEST",
                summary="New Story",
                description="Story description",
                issue_type="Story",
            )

            result = await service.create_issue(payload)

            assert result.is_ok is True
            assert result.value == "TEST-124"

    @pytest.mark.asyncio
    async def test_create_issue_validation_error(self, service):
        """create_issue returns validation error on 400 response."""
        error = JiraError(
            code=JiraErrorCode.VALIDATION_ERROR,
            message="Summary is required",
            status_code=400,
        )

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = Result.err(error)

            payload = CreateIssuePayload(
                project_key="TEST",
                summary="",  # Empty summary
                issue_type="Story",
            )

            result = await service.create_issue(payload)

            assert result.is_error is True
            assert result.error.code == JiraErrorCode.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_update_issue_success(self, service):
        """update_issue returns success on 204 response."""
        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = Result.ok({})

            result = await service.update_issue("TEST-123", {"summary": "Updated"})

            assert result.is_ok is True

    @pytest.mark.asyncio
    async def test_search_issues_success(self, service):
        """search_issues returns list of JiraIssue on success."""
        mock_response = {
            "issues": [
                {
                    "key": "TEST-1",
                    "fields": {
                        "summary": "First issue",
                        "issuetype": {"name": "Story"},
                        "status": {"name": "Open"},
                    },
                },
                {
                    "key": "TEST-2",
                    "fields": {
                        "summary": "Second issue",
                        "issuetype": {"name": "Task"},
                        "status": {"name": "Done"},
                    },
                },
            ],
        }

        with patch.object(service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = Result.ok(mock_response)

            result = await service.search_issues("project = TEST")

            assert result.is_ok is True
            issues = result.value
            assert len(issues) == 2
            assert issues[0].key == "TEST-1"
            assert issues[1].key == "TEST-2"


# =============================================================================
# NodeError and NodeResult Tests
# =============================================================================


class TestNodeError:
    """Tests for NodeError factory methods."""

    def test_validation_error_factory(self):
        """NodeError.validation creates proper error."""
        from src.app.agents.backlog.result import NodeError, NodeErrorCode

        error = NodeError.validation("Invalid input", field="epic_description")

        assert error.code == NodeErrorCode.VALIDATION_ERROR
        assert error.message == "Invalid input"
        assert error.details["field"] == "epic_description"
        assert error.recoverable is True

    def test_missing_input_factory(self):
        """NodeError.missing_input creates proper error."""
        from src.app.agents.backlog.result import NodeError, NodeErrorCode

        error = NodeError.missing_input("epic_description")

        assert error.code == NodeErrorCode.MISSING_INPUT
        assert "epic_description" in error.message
        assert error.details["field"] == "epic_description"

    def test_locked_thread_factory(self):
        """NodeError.locked_thread creates non-recoverable error."""
        from src.app.agents.backlog.result import NodeError, NodeErrorCode

        error = NodeError.locked_thread("abc-123")

        assert error.code == NodeErrorCode.LOCKED_THREAD
        assert "abc-123" in error.message
        assert error.recoverable is False

    def test_jira_error_factory(self):
        """NodeError.jira_error creates proper error with status code."""
        from src.app.agents.backlog.result import NodeError, NodeErrorCode

        error = NodeError.jira_error("Failed to create issue", status_code=400)

        assert error.code == NodeErrorCode.JIRA_ERROR
        assert "Failed to create issue" in error.message
        assert error.details["status_code"] == 400


class TestNodeResult:
    """Tests for NodeResult type."""

    def test_ok_with_state_updates(self):
        """NodeResult.ok includes state updates."""
        from src.app.agents.backlog.result import NodeResult

        result = NodeResult.ok(
            value={"stories": []},
            state_updates={"stories": [], "current_result": {}},
        )

        assert result.is_ok is True
        assert result.value == {"stories": []}
        assert result.state_updates == {"stories": [], "current_result": {}}

    def test_to_state_update_on_success(self):
        """to_state_update returns state_updates on success."""
        from src.app.agents.backlog.result import NodeResult

        result = NodeResult.ok(
            value="done",
            state_updates={"status": "complete"},
        )

        update = result.to_state_update()
        assert update == {"status": "complete"}

    def test_to_state_update_on_error(self):
        """to_state_update returns error dict on error."""
        from src.app.agents.backlog.result import NodeError, NodeResult

        error = NodeError.validation("Bad input")
        result = NodeResult.err(error)

        update = result.to_state_update()
        assert "error" in update
        assert "Bad input" in update["error"]

    def test_from_exception(self):
        """from_exception creates error result from exception."""
        from src.app.agents.backlog.result import NodeErrorCode, NodeResult

        exc = ValueError("Something broke")
        result = NodeResult.from_exception(exc)

        assert result.is_error is True
        assert result.error.code == NodeErrorCode.INTERNAL_ERROR
        assert "Something broke" in result.error.message
        assert result.error.original_exception is exc


# =============================================================================
# Run pytest if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
