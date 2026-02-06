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
from ..schemas import DecompositionResult, UserStory, Epic
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
                result = await self._mock_export(current_result, state)
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

    async def _mock_export(self, result: DecompositionResult, state: BacklogAgentState) -> dict[str, Any]:
        """Generate mock export result for testing."""
        logger.info("ExportNode: Using mock export")

        current_parent_epic_id = state.get("parent_epic_id")
        epic_created = False
        
        if not current_parent_epic_id and result.epic:
            current_parent_epic_id = "MOCK-EPIC-001"
            epic_created = True

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
                    "parent_epic": current_parent_epic_id,
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
            "message": f"Created {len(created_issues)} issues (mock)" + (" and new Epic" if epic_created else ""),
            "issues": created_issues,
            "epic_key": current_parent_epic_id,
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
        current_parent_epic_id = state.get("parent_epic_id")

        async with httpx.AsyncClient() as client:
            # Create parent Epic if missing (Phase 46)
            if not current_parent_epic_id and result.epic:
                try:
                    logger.info(f"ExportNode: Creating new Epic '{result.epic.title}'")
                    current_parent_epic_id = await self._create_jira_epic(
                        client=client,
                        base_url=base_url,
                        auth=auth,
                        project_key=project_key,
                        epic=result.epic
                    )
                    logger.info(f"ExportNode: New Epic created with key {current_parent_epic_id}")
                    # Include Epic in the created issues list for feedback (Phase 46)
                    created_issues.append({
                        "internal_id": "EPIC",
                        "jira_key": current_parent_epic_id,
                        "url": f"{base_url}/browse/{current_parent_epic_id}",
                        "status": "created",
                        "summary": result.epic.title,
                        "issuetype": self.config.JIRA_EPIC_ISSUE_TYPE
                    })
                except httpx.HTTPStatusError as e:
                    response_text = e.response.text
                    logger.error(f"ExportNode: Jira failure (400) creating Epic: {response_text}")
                    errors.append({
                        "story_id": "EPIC_CREATION",
                        "error": f"Failed to create parent Epic (Jira rejected payload): {response_text}"
                    })
                except Exception as e:
                    logger.error(f"ExportNode: Failed to create parent Epic: {e}")
                    errors.append({
                        "story_id": "EPIC_CREATION",
                        "error": f"Failed to create parent Epic: {str(e)}"
                    })

            # Create each story as a JIRA issue
            for story in result.stories:
                try:
                    issue = await self._create_jira_issue(
                        client=client,
                        base_url=base_url,
                        auth=auth,
                        project_key=project_key,
                        story=story,
                        parent_epic_id=current_parent_epic_id,
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
            "epic_key": current_parent_epic_id,
            "stories": result.stories, # Pass updated stories back
        }

    async def _create_jira_epic(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple[str, str],
        project_key: str,
        epic: Epic,
    ) -> str:
        """Create a new JIRA Epic and return its key."""
        fields = {
            "project": {"key": project_key},
            "issuetype": {"name": self.config.JIRA_EPIC_ISSUE_TYPE},
            "summary": epic.title,
            "description": epic.description,
            "labels": self.config.DEFAULT_TAGS or [],
        }

        # Only add Epic Name if explicitly configured (required for Company-managed, usually customfield_10011)
        # Skip for Team-managed projects where it causes 400 errors.
        if self.config.JIRA_EPIC_NAME_FIELD:
            fields[self.config.JIRA_EPIC_NAME_FIELD] = epic.title
        
        payload = {"fields": fields}
        
        url = f"{base_url}/rest/api/2/issue"
        logger.info(f"JIRA Epic Request: {payload}")
        response = await client.post(url, json=payload, auth=auth)
        
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Re-raise to be caught in _jira_export with more context
            raise
            
        data = response.json()
        return data["key"]

    async def _create_jira_issue(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple[str, str],
        project_key: str,
        story: UserStory,
        parent_epic_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a single JIRA issue."""
        # Start with standard fields
        fields = {
            "project": {"key": project_key},
            "issuetype": {"name": self.config.JIRA_ISSUE_TYPE},
            "summary": story.title,
            "labels": (story.tags or []) + (self.config.DEFAULT_TAGS or []),
        }

        # Handle parent Epic linking
        if parent_epic_id:
            # Note: Field name for Epic Link varies by JIRA instance (usually customfield_10014)
            # We use the config-defined field
            fields[self.config.JIRA_EPIC_LINK_FIELD] = parent_epic_id

        # Build description based on what's NOT mapped to custom fields
        description_parts = [story.description, ""]
        
        # Acceptance Criteria
        if story.acceptance_criteria:
            ac_text = "\n".join([f"* {ac.description}" for ac in story.acceptance_criteria])
            if self.config.JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA:
                fields[self.config.JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA] = ac_text
            else:
                description_parts.append("h3. Acceptance Criteria")
                description_parts.append(ac_text)
                description_parts.append("")

        # Technical Notes
        if story.technical_notes:
            tech_notes_text = "\n".join([f"* {note}" for note in story.technical_notes])
            if self.config.JIRA_FIELD_MAP_TECH_NOTES:
                fields[self.config.JIRA_FIELD_MAP_TECH_NOTES] = tech_notes_text
            else:
                description_parts.append("h3. Technical Notes")
                description_parts.append(tech_notes_text)
                description_parts.append("")

        # Edge Cases (Always in description for now)
        if story.edge_cases:
            description_parts.append("h3. Edge Cases")
            for ec in story.edge_cases:
                description_parts.append(f"* {ec}")
            description_parts.append("")

        fields["description"] = "\n".join(description_parts).strip()

        # Complexity / Story Points
        if story.estimated_complexity and self.config.JIRA_FIELD_MAP_COMPLEXITY:
            complexity_to_points = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}
            points = complexity_to_points.get(story.estimated_complexity)
            if points is not None:
                fields[self.config.JIRA_FIELD_MAP_COMPLEXITY] = points

        # Priority
        if story.priority and self.config.JIRA_FIELD_MAP_PRIORITY:
            # Map MoSCoW to Jira Priority (Example: must-have -> High)
            priority_map = {
                "must-have": "High",
                "should-have": "Medium",
                "could-have": "Low",
                "won't-have": "Lowest"
            }
            jira_priority = priority_map.get(story.priority)
            if jira_priority:
                fields[self.config.JIRA_FIELD_MAP_PRIORITY] = {"name": jira_priority}

        # Dependencies
        if story.dependencies and self.config.JIRA_FIELD_MAP_DEPENDENCIES:
            fields[self.config.JIRA_FIELD_MAP_DEPENDENCIES] = ", ".join(story.dependencies)

        payload = {"fields": fields}

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
