import logging
from typing import Any

import httpx

from ..core.config import settings
from .azure_openai import LLMService
from .base import BaseIndexer, BaseVectorStore

logger = logging.getLogger(__name__)


class JiraIndexer(BaseIndexer):
    """
    Indexer for Jira Data Center issue data.
    Implements efficient incremental sync patterns.
    """

    def __init__(self, vector_store: BaseVectorStore, llm_service: LLMService):
        self.vector_store = vector_store
        self.llm_service = llm_service
        self.base_url = settings.JIRA_URL
        self.username = settings.JIRA_USERNAME
        self.api_token = settings.JIRA_API_TOKEN

    async def _fetch_issues(self, jql: str, limit: int = 50, start_at: int = 0) -> list[dict[str, Any]]:
        """Fetch issues from Jira DC using the search API."""
        if not self.base_url or not self.api_token:
            logger.error("Jira configuration missing.")
            return []

        url = f"{self.base_url}/rest/api/2/search"
        auth = (self.username, self.api_token.get_secret_value())

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={
                    "jql": jql,
                    "maxResults": limit,
                    "startAt": start_at,
                    "fields": "summary,description,comment,status,updated",
                },
                auth=auth,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("issues", [])

    async def run(self, project_key: str, force: bool = False) -> dict[str, Any]:
        """
        Sync issues for a project.
        In a real scenario, we'd use 'updated > last_sync_time'.
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
