"""
Jira Indexer.
=============
Index issues from Atlassian Jira using JiraService.

Refactored to use the centralized JiraService for API calls,
providing retry logic and consistent error handling.
"""

import logging
from typing import Any

from ..core.config import settings
from ..services.jira_service import JiraConfig, JiraService
from .azure_openai import LLMService
from .base import BaseIndexer, BaseVectorStore

logger = logging.getLogger(__name__)


class JiraIndexer(BaseIndexer):
    """
    Indexer for Jira Data Center issue data.
    
    Uses JiraService for all API interactions, providing:
    - Retry logic with exponential backoff
    - Consistent error handling
    - Result type for explicit success/error handling
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        llm_service: LLMService,
        jira_service: JiraService | None = None,
    ):
        self.vector_store = vector_store
        self.llm_service = llm_service

        # Use injected service or create one from settings
        if jira_service:
            self._jira_service = jira_service
        else:
            config = JiraConfig.from_settings(settings)
            self._jira_service = JiraService(config) if config.is_configured else None

    async def _fetch_issues(self, jql: str, limit: int = 50, start_at: int = 0) -> list[dict[str, Any]]:
        """Fetch issues from Jira using JiraService.search_issues()."""
        if not self._jira_service:
            logger.error("Jira configuration missing or JiraService not available.")
            return []

        # Use JiraService's search_issues method
        result = await self._jira_service.search_issues(
            jql=jql,
            max_results=limit,
            start_at=start_at,
            fields=["summary", "description", "comment", "status", "updated"],
        )

        if result.is_error:
            logger.error(f"Failed to search issues: {result.error.message}")
            return []

        # Convert JiraIssue objects to dicts for backward compatibility
        return [
            {
                "key": issue.key,
                "fields": {
                    "summary": issue.summary,
                    "description": issue.description,
                    "status": {"name": issue.status},
                },
            }
            for issue in result.value
        ]

    async def run(self, project_key: str, force: bool = False) -> dict[str, Any]:
        """
        Sync issues for a project.
        
        Args:
            project_key: The Jira project key (e.g., "PROJ")
            force: If True, reindex all issues. Otherwise, incremental.
        """
        jql = f"project = {project_key}"
        if not force:
            # Placeholder for incremental logic
            # jql += " AND updated > -1d"
            pass

        issues = await self._fetch_issues(jql)
        logger.info(f"Fetched {len(issues)} issues for project {project_key}")

        indexed_count = 0
        for issue in issues:
            key = issue["key"]
            summary = issue["fields"].get("summary", "")
            description = issue["fields"].get("description", "")
            status = issue["fields"].get("status", {}).get("name", "Unknown")

            content = f"Jira Issue: {key}\nSummary: {summary}\nStatus: {status}\nDescription: {description}"

            # Embed the synthesized issue content
            embedding = await self.llm_service.get_embeddings(content)

            await self.vector_store.add_documents(
                [
                    {
                        "content": content,
                        "embedding": embedding,
                        "metadata": {"key": key, "type": "jira_issue"},
                        "source_id": key,
                    }
                ]
            )
            indexed_count += 1

        return {"project": project_key, "issues_indexed": indexed_count, "status": "success"}
