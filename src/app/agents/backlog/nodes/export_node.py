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
from ....core.db.database import local_session
from ...azure_openai import get_llm_service
from ...vector_stores import VectorStoreFactory
from ..config import BacklogAgentConfig
from ..schemas import DecompositionResult, Epic, UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class ExportNode:
    """
    Export decomposition to JIRA.

    Uses existing JIRA configuration from settings:
    - JIRA_URL
    - JIRA_USERNAME
    - JIRA_API_TOKEN

    Creates issues in JIRA and returns created issue keys.

    REFACTORED: Can now accept an injected JiraService for cleaner dependency
    management. Falls back to direct httpx calls if no service is provided.

    Usage:
        # With injected service (preferred)
        jira_service = JiraService(config)
        node = ExportNode(config=config, jira_service=jira_service)

        # Legacy (backwards compatible)
        node = ExportNode(config=BacklogAgentConfig(ENABLE_JIRA_EXPORT=True))
        updated_state = await node(state)
    """

    def __init__(
        self,
        config: BacklogAgentConfig | None = None,
        jira_service: Any = None,
    ):
        """
        Initialize ExportNode.

        Args:
            config: Agent configuration
            jira_service: Optional JiraService for dependency injection.
                          If provided, will be used for all Jira operations.
                          Falls back to direct httpx calls if not provided.
        """
        self.config = config or BacklogAgentConfig()
        self._jira_service = jira_service

    # =========================================================================
    # JiraService-based helpers (preferred when service is available)
    # =========================================================================

    def _has_jira_service(self) -> bool:
        """Check if JiraService is available for use."""
        return self._jira_service is not None

    def _get_labels(self, story_or_epic: UserStory | Epic) -> list[str]:
        """Combine and de-duplicate tags/labels, ensuring 'ai' is present."""
        tags = getattr(story_or_epic, "tags", []) or []
        default_tags = self.config.DEFAULT_TAGS or []
        all_labels = set(tags + default_tags + ["ai"])
        return sorted(all_labels)

    async def _create_epic_via_service(
        self,
        project_key: str,
        title: str,
        description: str,
        labels: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Create an epic using the injected JiraService.

        Returns dict with key, id, etc. on success, None on failure.
        """
        if not self._has_jira_service():
            return None

        from ....services.jira_service import CreateEpicPayload

        payload = CreateEpicPayload(
            project_key=project_key,
            summary=title,
            description=description,
            labels=labels or [],
        )

        result = await self._jira_service.create_epic(payload)
        if result.is_ok:
            return result.value
        else:
            logger.error(f"ExportNode: JiraService epic creation failed: {result.error}")
            return None

    async def _create_issue_via_service(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Story",
        parent_key: str | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Create an issue using the injected JiraService.

        Returns dict with key, id, etc. on success, None on failure.
        """
        if not self._has_jira_service():
            return None

        from ....services.jira_service import CreateIssuePayload

        payload = CreateIssuePayload(
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            parent_key=parent_key,
            labels=labels or [],
        )

        result = await self._jira_service.create_issue(payload)
        if result.is_ok:
            return result.value
        else:
            logger.error(f"ExportNode: JiraService issue creation failed: {result.error}")
            return None

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

                # 2. Audit Log (Phase 49)
                if result.get("status") in ["success", "partial_success"]:
                    await self._log_audit_event(state, result)

                # 3. Index to Azure AI Search (Phase 13)
                if result.get("status") in ["success", "partial_success"]:
                    await self._index_stories(current_result.stories)

            logger.info(f"ExportNode: Export completed - {result['status']}")

            is_locked = result.get("status") in ["success", "partial_success"]

            return {
                "export_result": result,
                "stories": result.get("stories", []),
                "current_result": current_result,
                "is_locked": is_locked,
                "error": None,
            }

        except Exception as e:
            logger.error(f"ExportNode: CRITICAL ERROR - {e}", exc_info=True)
            return {
                "export_result": {
                    "status": "error",
                    "message": str(e),
                },
                "error": f"Export failed: {str(e)}",
            }

    def _validate_jira_config(self) -> bool:
        """Check if JIRA configuration is complete."""
        has_url = bool(getattr(settings, "JIRA_URL", None))
        has_token = bool(getattr(settings, "JIRA_API_TOKEN", None))

        # Username is only strictly required for BASIC auth, not for PAT
        auth_mode = getattr(settings, "JIRA_AUTH_MODE", "basic")
        if auth_mode == "pat":
            return has_url and has_token

        return has_url and has_token and bool(getattr(settings, "JIRA_USERNAME", None))

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

    async def _jira_export_via_service(self, result: DecompositionResult, state: BacklogAgentState) -> dict[str, Any]:
        """
        Create issues in JIRA using the injected JiraService.

        This is the preferred method when JiraService is available.
        It provides retry logic, consistent error handling, and better observability.
        """
        if not self._jira_service:
            raise RuntimeError("JiraService not available")

        # Determine project key (Priority: Epic > State > Config > Default)
        project_key = (
            (result.epic.project_key if result.epic else None)
            or state.get("project_key")
            or self.config.JIRA_PROJECT_KEY
            or "PROJ"
        )

        base_url = settings.JIRA_URL
        created_issues = []
        errors = []

        # Robust Parent Key Handling
        current_parent_epic_id = state.get("parent_epic_id")
        if current_parent_epic_id and "-" not in current_parent_epic_id:
            logger.warning(f"ExportNode: Ignoring invalid parent_epic_id: {current_parent_epic_id}")
            current_parent_epic_id = None

        # 1. Handle Epic creation/update
        current_parent_epic_id = await self._export_epic(
            result, project_key, current_parent_epic_id, created_issues, errors, base_url
        )

        # 2. Handle Story creation/update
        await self._export_stories(
            result.stories,
            project_key,
            current_parent_epic_id,
            created_issues,
            errors,
            base_url,
            state,
        )

        status = "success" if not errors else "partial_success" if created_issues else "error"

        status = "success" if not errors else "partial_success" if created_issues else "error"

        # Update stories with Jira info
        jira_lookup = {issue["internal_id"]: issue for issue in created_issues}
        for story in result.stories:
            if story.id in jira_lookup:
                story.jira_key = jira_lookup[story.id]["jira_key"]
                story.jira_url = jira_lookup[story.id]["url"]

        return {
            "status": status,
            "message": f"Created {len(created_issues)} of {len(result.stories)} issues via JiraService",
            "issues": created_issues,
            "errors": errors,
            "epic_key": current_parent_epic_id,
            "stories": result.stories,
        }

    async def _export_epic(
        self,
        result: DecompositionResult,
        project_key: str,
        current_parent_epic_id: str | None,
        created_issues: list,
        errors: list,
        base_url: str,
    ) -> str | None:
        """Handle Epic creation or update."""
        from ....services.jira_service import CreateEpicPayload

        if current_parent_epic_id:
            if result.epic:
                try:
                    logger.info(f"ExportNode: Updating existing Epic {current_parent_epic_id} via service")
                    epic_data = result.epic.to_jira_format()
                    update_result = await self._jira_service.update_issue(
                        current_parent_epic_id,
                        {
                            "summary": epic_data["summary"],
                            "description": epic_data["description"],
                            "labels": self._get_labels(result.epic),
                        },
                    )
                    if update_result.is_error:
                        logger.warning(
                            f"ExportNode: Failed to update Epic {current_parent_epic_id}: {update_result.error}"
                        )
                except Exception as e:
                    logger.warning(f"ExportNode: Failed to update Epic {current_parent_epic_id}: {e}")
        elif result.epic:
            try:
                logger.info(f"ExportNode: Creating new Epic '{result.epic.title}' via service")
                epic_data = result.epic.to_jira_format()
                payload = CreateEpicPayload(
                    project_key=project_key,
                    summary=epic_data["summary"],
                    description=epic_data["description"],
                    labels=self._get_labels(result.epic),
                )
                epic_result = await self._jira_service.create_epic(payload)

                if epic_result.is_ok:
                    current_parent_epic_id = epic_result.value
                    logger.info(f"ExportNode: New Epic created with key {current_parent_epic_id}")
                    created_issues.append(
                        {
                            "internal_id": "EPIC",
                            "jira_key": current_parent_epic_id,
                            "url": f"{base_url}/browse/{current_parent_epic_id}",
                            "status": "created",
                            "summary": result.epic.title,
                            "issuetype": self.config.JIRA_EPIC_ISSUE_TYPE,
                        }
                    )
                else:
                    errors.append(
                        {
                            "story_id": "EPIC_CREATION",
                            "error": f"Failed to create Epic: {epic_result.error.message}",
                        }
                    )
            except Exception as e:
                logger.error(f"ExportNode: Failed to create Epic: {e}")
                errors.append({"story_id": "EPIC_CREATION", "error": str(e)})

        return current_parent_epic_id

    async def _export_stories(
        self,
        stories: list[UserStory],
        project_key: str,
        current_parent_epic_id: str | None,
        created_issues: list,
        errors: list,
        base_url: str,
        state: BacklogAgentState,
    ) -> None:
        """Handle multiple stories export."""
        for story in stories:
            await self._export_single_story(
                story,
                project_key,
                current_parent_epic_id,
                created_issues,
                errors,
                base_url,
                state,
            )

    async def _export_single_story(
        self,
        story: UserStory,
        project_key: str,
        current_parent_epic_id: str | None,
        created_issues: list,
        errors: list,
        base_url: str,
        state: BacklogAgentState,
    ) -> None:
        """Handle single story export/update."""
        from ....services.jira_service import CreateIssuePayload

        try:
            # 1. Build description
            description_parts = [story.description, ""]
            if story.acceptance_criteria:
                ac_text = "\n".join([f"* {ac.description}" for ac in story.acceptance_criteria])
                description_parts.append("h3. Acceptance Criteria")
                description_parts.append(ac_text)
                description_parts.append("")

            if story.technical_notes:
                tech_notes_text = "\n".join([f"* {note}" for note in story.technical_notes])
                description_parts.append("h3. Technical Notes")
                description_parts.append(tech_notes_text)
                description_parts.append("")

            if story.edge_cases:
                description_parts.append("h3. Edge Cases")
                for ec in story.edge_cases:
                    description_parts.append(f"* {ec}")
                description_parts.append("")

            if story.test_scenarios:
                description_parts.append("h3. QA Scenarios")
                for scenario in story.test_scenarios:
                    clean_scenario = scenario.replace("```gherkin", "").replace("```", "").strip()
                    description_parts.append("{code:gherkin}\n" + clean_scenario + "\n{code}")
                description_parts.append("")

            full_description = "\n".join(description_parts).strip()
            labels = self._get_labels(story)

            # 2. Update if key exists
            if story.jira_key:
                update_result = await self._jira_service.update_issue(
                    story.jira_key,
                    {
                        "summary": story.title,
                        "description": full_description,
                        "labels": labels,
                    },
                )
                if update_result.is_ok:
                    created_issues.append(
                        {
                            "internal_id": story.id,
                            "jira_key": story.jira_key,
                            "url": f"{base_url}/browse/{story.jira_key}",
                            "status": "updated",
                            "summary": story.title,
                        }
                    )
                    return
                # If update failed (e.g., 404), fall through to creation

            # 3. Create new issue
            target_type = state.get("target_issue_type") or self.config.JIRA_ISSUE_TYPE
            parent_key = current_parent_epic_id if target_type != self.config.JIRA_EPIC_ISSUE_TYPE else None

            payload = CreateIssuePayload(
                project_key=project_key,
                summary=story.title,
                description=full_description,
                issue_type=target_type,
                parent_key=parent_key,
                labels=labels,
            )

            create_result = await self._jira_service.create_issue(payload)
            if create_result.is_ok:
                created_issues.append(
                    {
                        "internal_id": story.id,
                        "jira_key": create_result.value,
                        "url": f"{base_url}/browse/{create_result.value}",
                        "status": "created",
                        "summary": story.title,
                    }
                )
            else:
                errors.append(
                    {
                        "story_id": story.id,
                        "error": create_result.error.message,
                    }
                )

        except Exception as e:
            logger.error(f"ExportNode: Failed to export story {story.id}: {e}")
            errors.append({"story_id": story.id, "error": str(e)})

    async def _jira_export(self, result: DecompositionResult, state: BacklogAgentState) -> dict[str, Any]:
        """
        Create issues in JIRA.

        Uses JiraService if available, falls back to direct httpx calls otherwise.
        """
        # Prefer JiraService when available (provides retry logic and consistent error handling)
        if self._has_jira_service():
            logger.info("ExportNode: Using JiraService for export")
            return await self._jira_export_via_service(result, state)

        logger.info("ExportNode: Using legacy httpx export (JiraService not available)")
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
            # 1. Handling Parent Epic (Create or Update)
            if current_parent_epic_id:
                # Epic exists, try to update it if we have fresh content
                if result.epic:
                    try:
                        logger.info(f"ExportNode: Updating existing Epic {current_parent_epic_id}")
                        await self._update_jira_issue(
                            client=client,
                            base_url=base_url,
                            auth=auth,
                            jira_key=current_parent_epic_id,
                            story_or_epic=result.epic,
                        )
                        # We don't add to created_issues as it's an update, but we could log it.
                    except Exception as e:
                        logger.warning(f"ExportNode: Failed to update Epic {current_parent_epic_id}: {e}")
            elif result.epic:
                # No parent epic, create new one
                try:
                    logger.info(f"ExportNode: Creating new Epic '{result.epic.title}'")
                    current_parent_epic_id = await self._create_jira_epic(
                        client=client, base_url=base_url, auth=auth, project_key=project_key, epic=result.epic
                    )
                    logger.info(f"ExportNode: New Epic created with key {current_parent_epic_id}")
                    created_issues.append(
                        {
                            "internal_id": "EPIC",
                            "jira_key": current_parent_epic_id,
                            "url": f"{base_url}/browse/{current_parent_epic_id}",
                            "status": "created",
                            "summary": result.epic.title,
                            "issuetype": self.config.JIRA_EPIC_ISSUE_TYPE,
                        }
                    )
                except httpx.HTTPStatusError as e:
                    response_text = e.response.text
                    logger.error(f"ExportNode: Jira failure (400) creating Epic: {response_text}")
                    errors.append(
                        {
                            "story_id": "EPIC_CREATION",
                            "error": f"Failed to create parent Epic (Jira rejected payload): {response_text}",
                        }
                    )
                except Exception as e:
                    logger.error(f"ExportNode: Failed to create parent Epic: {e}")
                    errors.append({"story_id": "EPIC_CREATION", "error": f"Failed to create parent Epic: {str(e)}"})

            # 2. Handling Stories (Create or Update)
            for story in result.stories:
                try:
                    if story.jira_key:
                        # Attempt Update
                        try:
                            await self._update_jira_issue(
                                client=client,
                                base_url=base_url,
                                auth=auth,
                                jira_key=story.jira_key,
                                story_or_epic=story,
                            )
                            created_issues.append(
                                {
                                    "internal_id": story.id,
                                    "jira_key": story.jira_key,
                                    "url": f"{base_url}/browse/{story.jira_key}",
                                    "status": "updated",
                                    "summary": story.title,
                                }
                            )
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                logger.warning(f"ExportNode: Issue {story.jira_key} not found (404), recreating.")
                                # Fallback to creation below
                                raise ValueError("Force Recreate")
                            else:
                                raise e
                    else:
                        raise ValueError("Create New")

                except (ValueError, Exception) as attempt_create_exception:
                    # Catch fallback or genuine create request
                    if (
                        isinstance(attempt_create_exception, ValueError)
                        and "Force Recreate" not in str(attempt_create_exception)
                        and "Create New" not in str(attempt_create_exception)
                    ):
                        # verification that this is not our control flow exception
                        errors.append({"story_id": story.id, "error": str(attempt_create_exception)})
                        continue

                    # Fallback to Creation
                    try:
                        issue = await self._create_jira_issue(
                            client=client,
                            base_url=base_url,
                            auth=auth,
                            project_key=project_key,
                            story=story,
                            parent_epic_id=current_parent_epic_id,
                            target_issue_type=state.get("target_issue_type") or self.config.JIRA_ISSUE_TYPE,
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
            "errors": errors,  # Phase 50 Fix: Pass errors back to API
            "epic_key": current_parent_epic_id,
            "stories": result.stories,  # Pass updated stories back
        }

    async def _log_audit_event(self, state: BacklogAgentState, result: dict[str, Any]) -> None:
        """Log the JIRA export event for compliance."""
        try:
            from ....services.audit_service import AuditService

            user_id = state.get("user_id")
            thread_id = state.get("thread_id")
            project_key = state.get("project_key")

            # Don't log if we don't have a user context (system/anonymous)
            # Actually, we should log anonymous actions too for security

            details = {
                "project_key": project_key,
                "issue_count": len(result.get("issues", [])),
                "status": result.get("status"),
                "epic_key": result.get("epic_key"),
                "issues": [i.get("jira_key") for i in result.get("issues", [])],
            }

            # Determine granular action
            action = "JIRA_EXPORT"
            issues = result.get("issues", [])
            if issues:
                if all(i.get("status") == "updated" for i in issues):
                    action = "JIRA_UPDATE"
                elif any(i.get("status") == "updated" for i in issues):
                    action = "JIRA_SYNC"

            # Fix Audit Logging: Use local_session directly as it is an async context manager
            # async_get_db is a generator and doesn't support 'async with' protocol directly
            async with local_session() as db:
                audit_service = AuditService(db)
                await audit_service.log_event(
                    action=action,
                    resource_type="EPIC",
                    resource_id=result.get("epic_key") or "N/A",
                    details=details,
                    user_id=user_id,
                    thread_id=thread_id,
                    status=result.get("status", "UNKNOWN"),
                )
        except Exception as e:
            logger.error(f"ExportNode: Failed to log audit event - {e}")

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
            "labels": self._get_labels(epic),
        }

        # Strategy 1: Try with Epic Name (Classic/Company-managed)
        if self.config.JIRA_EPIC_NAME_FIELD:
            fields[self.config.JIRA_EPIC_NAME_FIELD] = epic.title

        payload = {"fields": fields}
        url = f"{base_url}/rest/api/2/issue"

        try:
            logger.info(f"JIRA Epic Request (Attempt 1): {payload}")
            response = await client.post(url, json=payload, auth=auth)
            response.raise_for_status()
            return response.json()["key"]
        except httpx.HTTPStatusError as e:
            # If 400 Bad Request and it complains about the custom field (Epic Name)
            # It's likely a Team-managed project where this field is not allowed/needed.
            if e.response.status_code == 400 and self.config.JIRA_EPIC_NAME_FIELD in e.response.text:
                logger.warning(f"ExportNode: Epic Name field rejected. Retrying without it. Error: {e.response.text}")

                # Strategy 2: Retry without Epic Name
                del fields[self.config.JIRA_EPIC_NAME_FIELD]
                payload = {"fields": fields}
                logger.info(f"JIRA Epic Request (Attempt 2 - Retry): {payload}")

                response = await client.post(url, json=payload, auth=auth)
                response.raise_for_status()
                return response.json()["key"]
            else:
                raise e

    async def _create_jira_issue(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple[str, str],
        project_key: str,
        story: UserStory,
        parent_epic_id: str | None = None,
        target_issue_type: str | None = None,
    ) -> dict[str, Any]:
        """Create a single JIRA issue."""
        # Start with standard fields
        fields = {
            "project": {"key": project_key},
            "issuetype": {"name": target_issue_type or self.config.JIRA_ISSUE_TYPE},
            "summary": story.title,
            "labels": self._get_labels(story),
        }

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

        if story.edge_cases:
            description_parts.append("h3. Edge Cases")
            for ec in story.edge_cases:
                description_parts.append(f"* {ec}")
            description_parts.append("")

        # QA Scenarios
        if story.test_scenarios:
            description_parts.append("h3. QA Scenarios")
            for scenario in story.test_scenarios:
                clean_scenario = scenario.replace("```gherkin", "").replace("```", "").strip()
                description_parts.append("{code:gherkin}\n" + clean_scenario + "\n{code}")
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
            priority_map = {"must-have": "High", "should-have": "Medium", "could-have": "Low", "won't-have": "Lowest"}
            jira_priority = priority_map.get(story.priority)
            if jira_priority:
                fields[self.config.JIRA_FIELD_MAP_PRIORITY] = {"name": jira_priority}

        # Dependencies
        if story.dependencies and self.config.JIRA_FIELD_MAP_DEPENDENCIES:
            fields[self.config.JIRA_FIELD_MAP_DEPENDENCIES] = ", ".join(story.dependencies)

        # LINKING STRATEGY
        # 1. Try "Epic Link" (Classic Project)
        # 2. If 400 error, try "Parent" (Team/Next-Gen Project)

        # Prepare payload for Strategy 1
        payload = {"fields": fields.copy()}
        # Hierarchy Guard: Skip linking if we are creating an Epic (classic)
        if parent_epic_id and (target_issue_type or self.config.JIRA_ISSUE_TYPE) != self.config.JIRA_EPIC_ISSUE_TYPE:
            payload["fields"][self.config.JIRA_EPIC_LINK_FIELD] = parent_epic_id

        # LOG PAYLOAD FOR DEBUGGING
        logger.info(f"JIRA Payload (Attempt 1 - Epic Link): {payload}")

        try:
            response = await client.post(
                f"{base_url}/rest/api/2/issue",
                json=payload,
                auth=auth,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # If 400 and complains about Epic Link, try "Parent" field (Team-managed)
            if e.response.status_code == 400 and (
                self.config.JIRA_EPIC_LINK_FIELD in e.response.text or "Epic Link" in e.response.text
            ):
                logger.warning(
                    f"ExportNode: 'Epic Link' field rejected. Retrying with 'Parent' field. Error: {e.response.text}"
                )

                # Strategy 2: Use "parent" field
                if self.config.JIRA_EPIC_LINK_FIELD in payload["fields"]:
                    del payload["fields"][self.config.JIRA_EPIC_LINK_FIELD]

                # Hierarchy Guard: Skip linking if we are creating an Epic (Next-gen)
                if (target_issue_type or self.config.JIRA_ISSUE_TYPE) != self.config.JIRA_EPIC_ISSUE_TYPE:
                    payload["fields"]["parent"] = {"key": parent_epic_id}

                logger.info(f"JIRA Payload (Attempt 2 - Parent Link): {payload}")
                response = await client.post(
                    f"{base_url}/rest/api/2/issue",
                    json=payload,
                    auth=auth,
                    timeout=30.0,
                )
                response.raise_for_status()
            else:
                raise e

        data = response.json()
        return {
            "internal_id": story.id,
            "jira_key": data["key"],
            "url": f"{base_url}/browse/{data['key']}",
            "status": "created",
            "summary": story.title,
        }

    async def _update_jira_issue(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        auth: tuple[str, str],
        jira_key: str,
        story_or_epic: UserStory | Epic,
    ) -> None:
        """Update an existing JIRA issue."""
        # Detect if it's a Story or Epic to determine proper description field
        is_epic = isinstance(story_or_epic, Epic)

        fields = {
            "summary": story_or_epic.title,
            "labels": self._get_labels(story_or_epic),
        }

        # Build description
        description = story_or_epic.description

        # If it's a UserStory, append rich fields
        if not is_epic and isinstance(story_or_epic, UserStory):
            description_parts = [description, ""]

            # Acceptance Criteria
            if story_or_epic.acceptance_criteria:
                ac_text = "\n".join([f"* {ac.description}" for ac in story_or_epic.acceptance_criteria])
                # Note: We rely on standard description for updates to avoid complexity with custom fields mapping
                # unless explicitly configured. For now, we append to description.
                if self.config.JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA:
                    fields[self.config.JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA] = ac_text
                else:
                    description_parts.append("h3. Acceptance Criteria")
                    description_parts.append(ac_text)
                    description_parts.append("")

            # Technical Notes
            if story_or_epic.technical_notes:
                tech_notes_text = "\n".join([f"* {note}" for note in story_or_epic.technical_notes])
                if self.config.JIRA_FIELD_MAP_TECH_NOTES:
                    fields[self.config.JIRA_FIELD_MAP_TECH_NOTES] = tech_notes_text
                else:
                    description_parts.append("h3. Technical Notes")
                    description_parts.append(tech_notes_text)
                    description_parts.append("")

            # QA Scenarios
            if hasattr(story_or_epic, "test_scenarios") and story_or_epic.test_scenarios:
                description_parts.append("h3. QA Scenarios")
                for scenario in story_or_epic.test_scenarios:
                    clean_scenario = scenario.replace("```gherkin", "").replace("```", "").strip()
                    description_parts.append("{code:gherkin}\n" + clean_scenario + "\n{code}")
                description_parts.append("")

            description = "\n".join(description_parts).strip()

        fields["description"] = description

        # Complexity/Priority updates could be added here similar to creation

        payload = {"fields": fields}
        url = f"{base_url}/rest/api/2/issue/{jira_key}"

        logger.info(f"JIRA Update Request for {jira_key}: {payload}")
        response = await client.put(url, json=payload, auth=auth)
        response.raise_for_status()

    async def _index_stories(self, stories: list[UserStory]) -> None:
        """Index finalized stories into Azure AI Search for future memory."""
        logger.info(f"ExportNode: Indexing {len(stories)} stories into Azure AI Search")
        try:
            store = VectorStoreFactory.get_store(None)
            llm_service = get_llm_service()

            documents_to_index = []
            for story in stories:
                # Prepare content for embedding
                content = f"Title: {story.title}\nDescription: {story.description}\n"
                if story.acceptance_criteria:
                    content += "Acceptance Criteria:\n"
                    for ac in story.acceptance_criteria:
                        desc = ac.description if hasattr(ac, "description") else str(ac)
                        content += f"- {desc}\n"

                embedding = await llm_service.get_embeddings(content)

                documents_to_index.append(
                    {
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
                    }
                )

            await store.add_documents(documents_to_index)
            logger.info("ExportNode: Successfully indexed stories")
        except Exception as e:
            logger.warning(f"ExportNode: Failed to index stories - {e}")
        finally:
            if "store" in locals() and hasattr(store, "close"):
                await store.close()


# Convenience function for standalone testing
async def export_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for ExportNode."""
    node = ExportNode(config=config)
    return await node(state)
