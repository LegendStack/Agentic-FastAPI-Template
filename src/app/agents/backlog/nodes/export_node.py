"""
Export Node
===========
Optional JIRA issue creation via existing JiraIndexer config.
Creates issues with proper hierarchy (Epic → Stories).
"""

import logging
from typing import Any

import httpx

from ....core.config import settings
from ..config import BacklogAgentConfig
from ..schemas import DecompositionResult, UserStory
from ..state import BacklogAgentState
from ....core.db.database import async_get_db
from ...vector_stores import VectorStoreFactory
from ...azure_openai import LLMService

logger = logging.getLogger(__name__)


class ExportNode:
    """
    Export decomposition to JIRA.

    Uses existing JIRA configuration from settings:
    - JIRA_URL
    - JIRA_USERNAME
    - JIRA_API_TOKEN

    Creates issues in JIRA and returns created issue keys.

    Usage:
        node = ExportNode(config=BacklogAgentConfig(ENABLE_JIRA_EXPORT=True))
        updated_state = await node(state)
    """

    def __init__(self, config: BacklogAgentConfig | None = None):
        self.config = config or BacklogAgentConfig()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Export stories to JIRA.

        Args:
            state: Current agent state with current_result

        Returns:
            State update with export_result
        """
        logger.info("ExportNode: Starting JIRA export")

        if not self.config.ENABLE_JIRA_EXPORT:
            return {"error": "JIRA export is not enabled in configuration"}

        current_result = state.get("current_result")
        if not current_result:
            return {"error": "No decomposition result to export"}

        # Convert from dict if needed
        if isinstance(current_result, dict):
            current_result = DecompositionResult.model_validate(current_result)

        # Validate JIRA configuration
        if not self._validate_jira_config():
            return {
                "export_result": {
                    "status": "error",
                    "message": "JIRA configuration is incomplete. Set JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN.",
                },
                "error": "JIRA configuration incomplete",
            }

        try:
            if self.config.USE_MOCKS:
                result = await self._mock_export(current_result)
            else:
                # 1. Export to JIRA
                result = await self._jira_export(current_result, state)
                
                # 2. Index to Azure AI Search (Phase 13)
                if result.get("status") in ["success", "partial_success"]:
                    await self._index_stories(current_result.stories)

            logger.info(f"ExportNode: Export completed - {result['status']}")

            return {
                "export_result": result,
                "stories": result.get("stories", []),
                "current_result": current_result,
                "error": None,
            }

        except Exception as e:
            logger.error(f"ExportNode: Error - {e}")
            return {
                "export_result": {
                    "status": "error",
                    "message": str(e),
                },
                "error": f"Export failed: {str(e)}",
            }

    def _validate_jira_config(self) -> bool:
        """Check if JIRA configuration is complete."""
        return bool(
            getattr(settings, "JIRA_URL", None)
            and getattr(settings, "JIRA_USERNAME", None)
            and getattr(settings, "JIRA_API_TOKEN", None)
        )

    async def _mock_export(self, result: DecompositionResult) -> dict[str, Any]:
        """Generate mock export result for testing."""
        logger.info("ExportNode: Using mock export")

        created_issues = []
        for i, story in enumerate(result.stories):
            mock_key = f"MOCK-{1000 + i}"
            created_issues.append(
                {
                    "internal_id": story.id,
                    "jira_key": mock_key,
                    "url": f"https://jira.example.com/browse/{mock_key}",
                    "status": "created",
                    "summary": story.title,
                }
            )

        # Update stories in-place
        jira_lookup = {issue["internal_id"]: issue for issue in created_issues}
        for story in result.stories:
            if story.id in jira_lookup:
                story.jira_key = jira_lookup[story.id]["jira_key"]
                story.jira_url = jira_lookup[story.id]["url"]

        return {
            "status": "success",
            "message": f"Created {len(created_issues)} issues (mock)",
            "issues": created_issues,
            "epic_key": "MOCK-EPIC-001",
            "stories": result.stories,
        }

    async def _jira_export(self, result: DecompositionResult, state: BacklogAgentState) -> dict[str, Any]:
        """Create issues in JIRA."""
        base_url = settings.JIRA_URL
        auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
        
        # Determine project key (Priority: Epic > State > Config > Default)
        project_key = (
            (result.epic.project_key if result.epic else None) 
            or state.get("project_key") 
            or self.config.JIRA_PROJECT_KEY 
            or "PROJ"
        )

        created_issues = []
        errors = []

        async with httpx.AsyncClient() as client:
            # Create each story as a JIRA issue
            for story in result.stories:
                try:
                    issue = await self._create_jira_issue(
                        client=client,
                        base_url=base_url,
                        auth=auth,
                        project_key=project_key,
                        story=story,
                    )
                    created_issues.append(issue)
                except Exception as e:
                    errors.append(
                        {
                            "story_id": story.id,
                            "error": str(e),
                        }
                    )

        status = "success" if not errors else "partial_success" if created_issues else "error"

        # Update stories in-place with Jira info if successful
        jira_lookup = {issue["internal_id"]: issue for issue in created_issues}
        for story in result.stories:
            if story.id in jira_lookup:
                story.jira_key = jira_lookup[story.id]["jira_key"]
                story.jira_url = jira_lookup[story.id]["url"]

        return {
            "status": status,
            "message": f"Created {len(created_issues)} of {len(result.stories)} issues",
            "issues": created_issues,
            "errors": errors if errors else None,
            "stories": result.stories, # Pass updated stories back
        }

    async def _create_jira_issue(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple[str, str],
        project_key: str,
        story: UserStory,
    ) -> dict[str, Any]:
        """Create a single JIRA issue."""
        jira_format = story.to_jira_format()

        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": self.config.JIRA_ISSUE_TYPE},
                "summary": jira_format["summary"],
                "description": jira_format["description"],
                "labels": jira_format["labels"],
            }
        }

        # Add story points if complexity is available
        # DIVABLED FOR DEBUGGING - Custom fields often cause 400 errors if not configured in JIRA
        # complexity_to_points = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
        # if story.estimated_complexity:
        #     points = complexity_to_points.get(story.estimated_complexity)
        #     if points:
        #         # Note: Story points field varies by JIRA instance
        #         # This uses a common custom field name
        #         payload["fields"]["customfield_10016"] = points
        
        # LOG PAYLOAD FOR DEBUGGING
        logger.info(f"JIRA Payload: {payload}")

        response = await client.post(
            f"{base_url}/rest/api/2/issue",
            json=payload,
            auth=auth,
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        return {
            "internal_id": story.id,
            "jira_key": data["key"],
            "url": f"{base_url}/browse/{data['key']}",
            "status": "created",
            "summary": story.title,
        }

    async def _index_stories(self, stories: list[UserStory]) -> None:
        """Index finalized stories into Azure AI Search for future memory."""
        logger.info(f"ExportNode: Indexing {len(stories)} stories into Azure AI Search")
        try:
            store = VectorStoreFactory.get_store(None)
            llm_service = LLMService()
            
            documents_to_index = []
            for story in stories:
                # Prepare content for embedding
                content = f"Title: {story.title}\nDescription: {story.description}\n"
                if story.acceptance_criteria:
                    content += "Acceptance Criteria:\n"
                    for ac in story.acceptance_criteria:
                        desc = ac.description if hasattr(ac, 'description') else str(ac)
                        content += f"- {desc}\n"
                
                embedding = await llm_service.get_embeddings(content)
                
                documents_to_index.append({
                    "content": content,
                    "embedding": embedding,
                    "metadata": {
                        "title": story.title,
                        "story_id": story.id,
                        "type": "user_story",
                        "project_key": self.config.JIRA_PROJECT_KEY,
                    },
                    "source_id": f"jira_{story.id}",
                    "tenant_id": "default",
                })
            
            await store.add_documents(documents_to_index)
            logger.info("ExportNode: Successfully indexed stories")
        except Exception as e:
            logger.warning(f"ExportNode: Failed to index stories - {e}")


# Convenience function for standalone testing
async def export_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for ExportNode."""
    node = ExportNode(config=config)
    return await node(state)
