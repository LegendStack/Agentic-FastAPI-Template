"""
Mock Jira Service for Demo and Testing
"""

import logging
from typing import Any
from ....services.jira_service import Result, JiraIssue, JiraError, JiraErrorCode

logger = logging.getLogger(__name__)

class MockJiraService:
    """
    A fake Jira service that returns canned data for decomposition flow testing.
    """

    def __init__(self, config=None):
        self.config = config
        self.call_count = 0

    @staticmethod
    def description_to_text(description: Any) -> str:
        if not description: return ""
        if isinstance(description, str): return description
        return str(description)

    def get_issue_url(self, key: str) -> str:
        """Get the full web URL for a Jira issue (Mock)."""
        return f"https://mock-jira.com/browse/{key}"

    def get_issue_link(self, key: str) -> str:
        """Get a markdown link for a Jira issue (Mock)."""
        return f"[{key}]({self.get_issue_url(key)})"

    async def get_issue(self, key: str) -> Result[JiraIssue]:
        logger.info(f"MockJiraService: Getting issue {key}")
        
        # Canned response for KAN-20
        if "KAN-20" in key:
            issue = JiraIssue(
                key="KAN-20",
                summary="Initial Story Decomposition Demo",
                description="This is a sample story description that needs to be broken down into technical tasks for the team.",
                issue_type="Story",
                status="To Do",
                priority="Medium",
                project_key="KAN",
                url=f"https://mock-jira.com/browse/KAN-20"
            )
            return Result.ok(issue)
        
        return Result.err(JiraError(code=JiraErrorCode.NOT_FOUND, message=f"Issue {key} not found"))

    async def create_issue(self, payload: Any) -> Result[str]:
        self.call_count += 1
        key = f"KAN-{100 + self.call_count}"
        logger.info(f"MockJiraService: Created issue {key}")
        return Result.ok(key)

    async def get_user_by_email(self, email: str) -> Result[str]:
        logger.info(f"MockJiraService: Looking up user {email}")
        return Result.ok("mock-user-id-123")

    async def close(self) -> None:
        pass
