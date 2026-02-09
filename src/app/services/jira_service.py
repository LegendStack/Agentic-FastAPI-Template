"""
Jira Service
============
Unified Jira API client with proper error handling, retry logic,
and dependency injection support.

This service replaces direct httpx calls scattered across the codebase
(ExportNode, ContextHydrator, jira.py API routes) with a single,
testable abstraction.

Example Usage:
    # With dependency injection
    jira = JiraService(config=JiraConfig.from_settings())

    # Get an issue
    result = await jira.get_issue("PDLC-24")
    if result.is_ok:
        issue = result.value
        print(f"Found: {issue.summary}")
    else:
        print(f"Error: {result.error.message}")

    # Create an issue
    payload = CreateIssuePayload(
        project_key="PDLC",
        summary="New story",
        description="As a user...",
        issue_type="Story",
    )
    result = await jira.create_issue(payload)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class JiraConfig:
    """
    Centralized Jira configuration.

    All Jira-related settings in one place, validated at startup.
    """

    base_url: str
    username: str
    api_token: str
    default_project_key: str | None = None

    # Issue type names (may vary per Jira instance)
    epic_issue_type: str = "Epic"
    story_issue_type: str = "Story"
    task_issue_type: str = "Task"

    # Custom field IDs (Jira Cloud defaults)
    epic_name_field: str | None = "customfield_10011"
    epic_link_field: str | None = "customfield_10014"
    parent_field: str | None = "parent"  # Next-gen projects use this

    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_settings(cls) -> JiraConfig:
        """Create JiraConfig from application settings."""
        if not settings.JIRA_URL:
            raise JiraConfigurationError("JIRA_URL is not configured")
        if not settings.JIRA_API_TOKEN:
            raise JiraConfigurationError("JIRA_API_TOKEN is not configured")

        return cls(
            base_url=settings.JIRA_URL.rstrip("/"),
            username=settings.JIRA_USERNAME or "",
            api_token=settings.JIRA_API_TOKEN.get_secret_value(),
            default_project_key=settings.JIRA_PROJECTS[0] if settings.JIRA_PROJECTS else None,
            epic_issue_type=settings.JIRA_EPIC_ISSUE_TYPE,
            epic_name_field=settings.JIRA_EPIC_NAME_FIELD,
        )

    @property
    def auth(self) -> tuple[str, str]:
        """Get auth tuple for httpx."""
        return (self.username, self.api_token)

    @property
    def is_configured(self) -> bool:
        """Check if Jira is properly configured."""
        return bool(self.base_url and self.api_token)


# =============================================================================
# Error Types
# =============================================================================


class JiraErrorCode(str, Enum):
    """Categorized error codes for Jira operations."""

    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    AUTHENTICATION_ERROR = "authentication_error"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"


@dataclass
class JiraError:
    """
    Structured error from a Jira operation.

    Provides detailed information for logging and user feedback.
    """

    code: JiraErrorCode
    message: str
    status_code: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    original_exception: Exception | None = None

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.code.value}] HTTP {self.status_code}: {self.message}"
        return f"[{self.code.value}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class JiraConfigurationError(Exception):
    """Raised when Jira configuration is missing or invalid."""

    pass


# =============================================================================
# Result Type
# =============================================================================


@dataclass
class Result(Generic[T]):
    """
    A Result type for operations that can fail.

    Inspired by Rust's Result<T, E> type. Forces explicit error handling.

    Example:
        result = await jira.get_issue("KEY-123")
        if result.is_ok:
            issue = result.value
        else:
            logger.error(f"Failed: {result.error}")
    """

    _value: T | None = None
    _error: JiraError | None = None

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def is_error(self) -> bool:
        return self._error is not None

    @property
    def value(self) -> T:
        """Get the value. Raises if result is an error."""
        if self._error is not None:
            raise ValueError(f"Cannot get value from error result: {self._error}")
        return self._value  # type: ignore

    @property
    def error(self) -> JiraError:
        """Get the error. Raises if result is ok."""
        if self._error is None:
            raise ValueError("Cannot get error from ok result")
        return self._error

    def unwrap_or(self, default: T) -> T:
        """Get value or return default if error."""
        return self._value if self.is_ok else default

    def map(self, fn) -> Result:
        """Transform the value if ok, pass through error otherwise."""
        if self.is_ok:
            return Result.ok(fn(self._value))
        return self

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        """Create a successful result."""
        return cls(_value=value)

    @classmethod
    def err(cls, error: JiraError) -> Result[T]:
        """Create an error result."""
        return cls(_error=error)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class JiraIssue:
    """Represents a Jira issue with commonly used fields."""

    key: str
    summary: str
    description: str | None = None
    issue_type: str | None = None
    status: str | None = None
    priority: str | None = None
    labels: list[str] = field(default_factory=list)
    parent_key: str | None = None
    project_key: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: dict[str, Any], base_url: str = "") -> JiraIssue:
        """Parse a Jira API response into a JiraIssue."""
        fields = data.get("fields", {})
        key = data.get("key", "")

        # Extract parent key (works for both classic and next-gen projects)
        parent_key = None
        if parent := fields.get("parent"):
            parent_key = parent.get("key")

        return cls(
            key=key,
            summary=fields.get("summary", ""),
            description=fields.get("description"),
            issue_type=fields.get("issuetype", {}).get("name"),
            status=fields.get("status", {}).get("name"),
            priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
            labels=fields.get("labels", []),
            parent_key=parent_key,
            project_key=fields.get("project", {}).get("key"),
            url=f"{base_url}/browse/{key}" if base_url else None,
            raw=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "summary": self.summary,
            "description": self.description,
            "issue_type": self.issue_type,
            "status": self.status,
            "priority": self.priority,
            "labels": self.labels,
            "parent_key": self.parent_key,
            "project_key": self.project_key,
            "url": self.url,
        }


@dataclass
class CreateIssuePayload:
    """Payload for creating a Jira issue."""

    project_key: str
    summary: str
    issue_type: str = "Story"
    description: str | None = None
    parent_key: str | None = None
    labels: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_jira_payload(self, config: JiraConfig) -> dict[str, Any]:
        """Convert to Jira API format."""
        fields: dict[str, Any] = {
            "project": {"key": self.project_key},
            "summary": self.summary,
            "issuetype": {"name": self.issue_type},
        }

        if self.description:
            # Jira Cloud uses ADF format for description
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": self.description}],
                    }
                ],
            }

        if self.labels:
            fields["labels"] = self.labels

        # Handle parent linking (next-gen projects)
        if self.parent_key:
            fields["parent"] = {"key": self.parent_key}

        # Add custom fields
        for field_id, value in self.custom_fields.items():
            fields[field_id] = value

        return {"fields": fields}


@dataclass
class CreateEpicPayload:
    """Payload for creating a Jira Epic."""

    project_key: str
    summary: str
    description: str | None = None
    labels: list[str] = field(default_factory=list)

    def to_jira_payload(self, config: JiraConfig) -> dict[str, Any]:
        """Convert to Jira API format for Epic creation."""
        fields: dict[str, Any] = {
            "project": {"key": self.project_key},
            "summary": self.summary,
            "issuetype": {"name": config.epic_issue_type},
        }

        if self.description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": self.description}],
                    }
                ],
            }

        if self.labels:
            fields["labels"] = self.labels

        # Add Epic Name field if configured
        if config.epic_name_field:
            fields[config.epic_name_field] = self.summary

        return {"fields": fields}


# =============================================================================
# Jira Service
# =============================================================================


class JiraService:
    """
    Unified Jira API client with retry logic and consistent error handling.

    This service is the single point of contact for all Jira operations.
    It handles authentication, retries, and response parsing.

    Example:
        config = JiraConfig.from_settings()
        jira = JiraService(config)

        result = await jira.get_issue("PDLC-24")
        if result.is_ok:
            print(result.value.summary)
    """

    def __init__(self, config: JiraConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                auth=self.config.auth,
                timeout=self.config.request_timeout_seconds,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> JiraService:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - closes the client."""
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> Result[dict[str, Any]]:
        """
        Make an HTTP request with retry logic.

        Returns a Result containing the JSON response or an error.
        """
        client = await self._get_client()
        last_error: JiraError | None = None

        for attempt in range(self.config.max_retries):
            try:
                response = await client.request(
                    method=method,
                    url=path,
                    json=json,
                    params=params,
                )

                # Handle success
                if response.status_code in (200, 201, 204):
                    if response.status_code == 204:
                        return Result.ok({})
                    return Result.ok(response.json())

                # Handle specific error codes
                error = self._parse_error(response)

                # Don't retry client errors (except rate limiting)
                if response.status_code < 500 and response.status_code != 429:
                    return Result.err(error)

                last_error = error

            except httpx.TimeoutException as e:
                last_error = JiraError(
                    code=JiraErrorCode.TIMEOUT,
                    message=f"Request timed out after {self.config.request_timeout_seconds}s",
                    original_exception=e,
                )
            except httpx.ConnectError as e:
                last_error = JiraError(
                    code=JiraErrorCode.CONNECTION_ERROR,
                    message=f"Failed to connect to Jira: {e}",
                    original_exception=e,
                )
            except Exception as e:
                last_error = JiraError(
                    code=JiraErrorCode.UNKNOWN,
                    message=f"Unexpected error: {e}",
                    original_exception=e,
                )

            # Wait before retry (exponential backoff)
            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_delay_seconds * (2**attempt)
                logger.warning(f"JiraService: Retry {attempt + 1}/{self.config.max_retries} after {delay}s")
                await asyncio.sleep(delay)

        return Result.err(
            last_error
            or JiraError(
                code=JiraErrorCode.UNKNOWN,
                message="Request failed after all retries",
            )
        )

    def _parse_error(self, response: httpx.Response) -> JiraError:
        """Parse an error response from Jira."""
        status = response.status_code

        # Try to extract error details from response
        details = {}
        message = f"HTTP {status}"
        try:
            data = response.json()
            if "errorMessages" in data:
                messages = data.get("errorMessages", [])
                errors = data.get("errors", {})
                message = "; ".join(messages) if messages else str(errors)
                details = {"errorMessages": messages, "errors": errors}
            elif "message" in data:
                message = data["message"]
        except Exception:
            message = response.text[:200] if response.text else f"HTTP {status}"

        # Map status code to error code
        code_map = {
            400: JiraErrorCode.VALIDATION_ERROR,
            401: JiraErrorCode.AUTHENTICATION_ERROR,
            403: JiraErrorCode.PERMISSION_DENIED,
            404: JiraErrorCode.NOT_FOUND,
            429: JiraErrorCode.RATE_LIMITED,
        }
        code = code_map.get(status, JiraErrorCode.SERVER_ERROR if status >= 500 else JiraErrorCode.UNKNOWN)

        return JiraError(
            code=code,
            message=message,
            status_code=status,
            details=details,
        )

    # =========================================================================
    # Public API Methods
    # =========================================================================

    async def get_issue(self, key: str) -> Result[JiraIssue]:
        """
        Get a Jira issue by key.

        Args:
            key: The issue key (e.g., "PDLC-24")

        Returns:
            Result containing JiraIssue or error
        """
        logger.info(f"JiraService: Getting issue {key}")

        result = await self._request("GET", f"/rest/api/3/issue/{key}")

        if result.is_ok:
            issue = JiraIssue.from_api_response(result.value, self.config.base_url)
            logger.info(f"JiraService: Found issue {key}: {issue.summary[:50]}")
            return Result.ok(issue)

        return Result.err(result.error)

    async def create_issue(self, payload: CreateIssuePayload) -> Result[str]:
        """
        Create a new Jira issue.

        Args:
            payload: The issue creation payload

        Returns:
            Result containing the new issue key or error
        """
        logger.info(f"JiraService: Creating {payload.issue_type} in {payload.project_key}")

        jira_payload = payload.to_jira_payload(self.config)
        result = await self._request("POST", "/rest/api/3/issue", json=jira_payload)

        if result.is_ok:
            key = result.value.get("key", "")
            logger.info(f"JiraService: Created issue {key}")
            return Result.ok(key)

        logger.error(f"JiraService: Failed to create issue: {result.error}")
        return Result.err(result.error)

    async def create_epic(self, payload: CreateEpicPayload) -> Result[str]:
        """
        Create a new Jira Epic.

        Handles both classic and next-gen project configurations.

        Args:
            payload: The epic creation payload

        Returns:
            Result containing the new epic key or error
        """
        logger.info(f"JiraService: Creating Epic in {payload.project_key}")

        jira_payload = payload.to_jira_payload(self.config)
        result = await self._request("POST", "/rest/api/3/issue", json=jira_payload)

        if result.is_ok:
            key = result.value.get("key", "")
            logger.info(f"JiraService: Created Epic {key}")
            return Result.ok(key)

        # If Epic Name field failed, retry without it
        if result.error.code == JiraErrorCode.VALIDATION_ERROR and self.config.epic_name_field:
            logger.warning("JiraService: Retrying Epic creation without Epic Name field")
            del jira_payload["fields"][self.config.epic_name_field]
            result = await self._request("POST", "/rest/api/3/issue", json=jira_payload)

            if result.is_ok:
                key = result.value.get("key", "")
                logger.info(f"JiraService: Created Epic {key} (without Epic Name field)")
                return Result.ok(key)

        logger.error(f"JiraService: Failed to create Epic: {result.error}")
        return Result.err(result.error)

    async def update_issue(self, key: str, fields: dict[str, Any]) -> Result[None]:
        """
        Update an existing Jira issue.

        Args:
            key: The issue key to update
            fields: Fields to update

        Returns:
            Result indicating success or error
        """
        logger.info(f"JiraService: Updating issue {key}")

        result = await self._request("PUT", f"/rest/api/3/issue/{key}", json={"fields": fields})

        if result.is_ok:
            logger.info(f"JiraService: Updated issue {key}")
            return Result.ok(None)

        logger.error(f"JiraService: Failed to update issue {key}: {result.error}")
        return Result.err(result.error)

    async def search_issues(self, jql: str, max_results: int = 50) -> Result[list[JiraIssue]]:
        """
        Search for issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results

        Returns:
            Result containing list of issues or error
        """
        logger.info(f"JiraService: Searching with JQL: {jql[:100]}...")

        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "description", "status", "issuetype", "priority", "labels", "parent", "project"],
        }

        result = await self._request("POST", "/rest/api/3/search/jql", json=payload)

        if result.is_ok:
            issues = [
                JiraIssue.from_api_response(issue, self.config.base_url) for issue in result.value.get("issues", [])
            ]
            logger.info(f"JiraService: Found {len(issues)} issues")
            return Result.ok(issues)

        return Result.err(result.error)

    async def get_project(self, key: str) -> Result[dict[str, Any]]:
        """
        Get project details.

        Args:
            key: Project key

        Returns:
            Result containing project data or error
        """
        logger.info(f"JiraService: Getting project {key}")
        return await self._request("GET", f"/rest/api/3/project/{key}")

    async def bulk_create_issues(
        self,
        payloads: list[CreateIssuePayload],
    ) -> Result[list[dict[str, Any]]]:
        """
        Create multiple issues in a single batch request.

        Uses Jira's bulk issue creation API for efficiency.

        Args:
            payloads: List of issue creation payloads

        Returns:
            Result containing list of created issue data or error
        """
        if not payloads:
            return Result.ok([])

        logger.info(f"JiraService: Bulk creating {len(payloads)} issues")

        issues = [p.to_jira_payload(self.config) for p in payloads]
        result = await self._request(
            "POST",
            "/rest/api/3/issue/bulk",
            json={"issueUpdates": issues},
        )

        if result.is_ok:
            created = result.value.get("issues", [])
            errors = result.value.get("errors", [])

            if errors:
                logger.warning(f"JiraService: Bulk create had {len(errors)} errors")

            logger.info(f"JiraService: Bulk created {len(created)} issues")
            return Result.ok(created)

        logger.error(f"JiraService: Bulk create failed: {result.error}")
        return Result.err(result.error)

    async def get_project_metadata(self, project_key: str) -> Result[dict[str, Any]]:
        """
        Get project metadata including issue types and custom fields.

        Useful for determining available issue types and required fields.

        Args:
            project_key: The project key

        Returns:
            Result containing metadata or error
        """
        logger.info(f"JiraService: Getting metadata for project {project_key}")

        result = await self._request(
            "GET",
            "/rest/api/3/issue/createmeta",
            params={"projectKeys": project_key, "expand": "projects.issuetypes.fields"},
        )

        if result.is_ok:
            projects = result.value.get("projects", [])
            if projects:
                return Result.ok(projects[0])
            return Result.ok({})

        return Result.err(result.error)

    async def transition_issue(
        self,
        key: str,
        transition_name: str,
    ) -> Result[None]:
        """
        Transition an issue to a new status.

        Args:
            key: Issue key to transition
            transition_name: Name of the transition (e.g., "In Progress", "Done")

        Returns:
            Result indicating success or error
        """
        logger.info(f"JiraService: Transitioning {key} to '{transition_name}'")

        # First, get available transitions
        transitions_result = await self._request(
            "GET",
            f"/rest/api/3/issue/{key}/transitions",
        )

        if transitions_result.is_error:
            return Result.err(transitions_result.error)

        # Find the transition by name
        transitions = transitions_result.value.get("transitions", [])
        target = None
        for t in transitions:
            if t.get("name", "").lower() == transition_name.lower():
                target = t
                break

        if not target:
            available = [t.get("name") for t in transitions]
            return Result.err(
                JiraError(
                    code=JiraErrorCode.VALIDATION_ERROR,
                    message=f"Transition '{transition_name}' not found. Available: {available}",
                )
            )

        # Execute the transition
        result = await self._request(
            "POST",
            f"/rest/api/3/issue/{key}/transitions",
            json={"transition": {"id": target["id"]}},
        )

        if result.is_ok:
            logger.info(f"JiraService: Transitioned {key} to '{transition_name}'")
            return Result.ok(None)

        return Result.err(result.error)

    async def get_issue_types(self, project_key: str) -> Result[list[dict[str, Any]]]:
        """
        Get available issue types for a project.

        Args:
            project_key: The project key

        Returns:
            Result containing list of issue type dicts or error
        """
        logger.info(f"JiraService: Getting issue types for {project_key}")

        result = await self._request(
            "GET",
            f"/rest/api/3/project/{project_key}",
        )

        if result.is_ok:
            issue_types = result.value.get("issueTypes", [])
            return Result.ok(issue_types)

        return Result.err(result.error)


# =============================================================================
# Factory Function
# =============================================================================


def get_jira_service() -> JiraService:
    """
    Factory function to create a JiraService instance.

    Used for dependency injection in FastAPI.
    """
    config = JiraConfig.from_settings()
    return JiraService(config)
