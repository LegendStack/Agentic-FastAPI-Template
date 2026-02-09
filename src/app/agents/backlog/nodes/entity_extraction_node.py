"""
Entity Extraction Node
======================
Extracts Jira entities (issue keys, project keys) from user messages
and hydrates them with context from the Jira API.

This node runs early in the pipeline to enrich the agent's context
before intent classification and processing.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Regex patterns for Jira entities
JIRA_ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
JIRA_PROJECT_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\b(?!\s*-\d)")


@dataclass
class ExtractedEntity:
    """Represents an extracted Jira entity from user input."""

    entity_type: str  # "issue", "project", "epic"
    key: str  # e.g., "KAN-123" or "KAN"
    raw_mention: str  # Original text span
    confidence: float = 1.0  # Extraction confidence
    hydrated_context: dict = field(default_factory=dict)  # Fetched details

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "key": self.key,
            "raw_mention": self.raw_mention,
            "confidence": self.confidence,
            "hydrated_context": self.hydrated_context,
        }


class EntityExtractor:
    """
    Extracts Jira entities from user messages.

    Supports:
    - Issue keys (KAN-123, PROJ-456)
    - Project keys (KAN, PROJ) when mentioned standalone
    """

    def extract(self, text: str) -> list[ExtractedEntity]:
        """
        Extract all Jira entities from the given text.

        Args:
            text: User message or epic description

        Returns:
            List of extracted entities, ordered by appearance
        """
        entities = []
        seen_keys = set()

        # Extract issue keys (higher priority)
        for match in JIRA_ISSUE_KEY_PATTERN.finditer(text):
            key = match.group(1)
            if key not in seen_keys:
                entities.append(
                    ExtractedEntity(
                        entity_type="issue",
                        key=key,
                        raw_mention=match.group(0),
                        confidence=1.0,
                    )
                )
                seen_keys.add(key)

        # Extract standalone project keys (lower priority, only if not part of an issue key)
        # This is more nuanced - we only want clear project references
        # like "in project KAN" or "KAN project"
        project_indicators = ["project", "board", "backlog"]
        text_lower = text.lower()

        for indicator in project_indicators:
            if indicator in text_lower:
                # Look for project key near the indicator
                for match in JIRA_PROJECT_KEY_PATTERN.finditer(text):
                    key = match.group(1)
                    # Check if this key isn't already captured as part of an issue
                    if key not in seen_keys and not any(key == e.key.split("-")[0] for e in entities):
                        # Verify it's near a project indicator
                        pos = match.start()
                        context = text_lower[max(0, pos - 20) : pos + len(key) + 20]
                        if any(ind in context for ind in project_indicators):
                            entities.append(
                                ExtractedEntity(
                                    entity_type="project",
                                    key=key,
                                    raw_mention=match.group(0),
                                    confidence=0.8,  # Lower confidence for inferred projects
                                )
                            )
                            seen_keys.add(key)

        logger.info(f"EntityExtractor: Extracted {len(entities)} entities: {[e.key for e in entities]}")
        return entities

    def extract_primary_issue(self, text: str) -> ExtractedEntity | None:
        """
        Extract the primary issue key from text.

        Returns the first issue mentioned, which is typically the main subject.
        """
        entities = self.extract(text)
        issues = [e for e in entities if e.entity_type == "issue"]
        return issues[0] if issues else None


class ContextHydrator:
    """
    Hydrates extracted entities with context from Jira API.

    This class fetches issue details, parent relationships, and
    child issues to provide rich context for the agent.

    REFACTORED: Now uses injected JiraService instead of circular HTTP calls.
    """

    def __init__(self, jira_service: Any = None):
        """
        Initialize the context hydrator.

        Args:
            jira_service: JiraService instance for fetching issue details.
                          If None, hydration will be skipped gracefully.
        """
        self._jira_service = jira_service

    async def _get_issue_from_service(self, issue_key: str) -> dict | None:
        """
        Fetch issue details using the injected JiraService.

        Falls back gracefully if no service is available.
        """
        if self._jira_service is None:
            logger.warning(f"ContextHydrator: No JiraService available, skipping hydration for {issue_key}")
            return None

        try:
            # Use the injected JiraService
            result = await self._jira_service.get_issue(issue_key)

            if result.is_ok:
                issue = result.value
                logger.info(f"ContextHydrator: Got issue {issue_key}: {issue.summary[:50]}")
                # Convert JiraIssue to dict format expected by hydration logic
                return {
                    "key": issue.key,
                    "summary": issue.summary,
                    "description": issue.description,
                    "issue_type": issue.issue_type,
                    "status": issue.status,
                    "priority": issue.priority,
                    "labels": issue.labels,
                    "parent": {"key": issue.parent_key} if issue.parent_key else None,
                }
            else:
                logger.warning(f"ContextHydrator: Failed to fetch {issue_key}: {result.error}")
                return None

        except Exception as e:
            logger.error(f"ContextHydrator: Error fetching {issue_key}: {e}")
            return None

    async def hydrate_entities(
        self,
        entities: list[ExtractedEntity],
        include_parent: bool = True,
        include_children: bool = False,
        include_linked: bool = False,
    ) -> list[ExtractedEntity]:
        """
        Hydrate entities with context from Jira.

        Args:
            entities: List of extracted entities to hydrate
            include_parent: Whether to fetch parent issue/epic
            include_children: Whether to fetch child issues
            include_linked: Whether to fetch linked issues

        Returns:
            Same entities with hydrated_context populated
        """
        logger.info(f"ContextHydrator: Starting hydration for {len(entities)} entities: {[e.key for e in entities]}")
        import asyncio

        # Hydrate all issue entities in parallel
        async def hydrate_one(entity: ExtractedEntity) -> ExtractedEntity:
            if entity.entity_type != "issue":
                return entity

            try:
                # Fetch issue details via injected JiraService
                issue = await self._get_issue_from_service(entity.key)
                if issue:
                    entity.hydrated_context = {
                        "key": issue.get("key") or entity.key,
                        "summary": issue.get("summary"),
                        "description": issue.get("description"),
                        "issuetype": issue.get("issue_type") or issue.get("issuetype"),
                        "status": issue.get("status"),
                        "priority": issue.get("priority"),
                        "labels": issue.get("labels", []),
                        "parent": None,
                        "children": [],
                    }

                    # Check for parent info in response
                    if include_parent and issue.get("parent"):
                        parent = issue.get("parent")
                        entity.hydrated_context["parent"] = {
                            "key": parent.get("key"),
                            "summary": parent.get("summary"),
                        }

                    logger.info(
                        f"ContextHydrator: Hydrated {entity.key} - {entity.hydrated_context.get('summary', 'N/A')}"
                    )

            except Exception as e:
                logger.error(f"ContextHydrator: Failed to hydrate {entity.key}: {e}")

            return entity

        # Run all hydrations in parallel
        hydrated = await asyncio.gather(*[hydrate_one(e) for e in entities])
        return list(hydrated)

    def format_context_for_prompt(self, entities: list[ExtractedEntity]) -> str:
        """
        Format hydrated entities into a context block for LLM prompts.

        Args:
            entities: Hydrated entities

        Returns:
            Formatted markdown context string
        """
        if not entities:
            return ""

        context_parts = []

        for entity in entities:
            if not entity.hydrated_context:
                continue

            ctx = entity.hydrated_context
            issue_type = ctx.get("issuetype", "Issue")
            summary = ctx.get("summary", "N/A")
            description = ctx.get("description") or "No description"

            part = f"""## Referenced {issue_type}: {entity.key}
**Summary**: {summary}
**Status**: {ctx.get("status", "Unknown")}
**Labels**: {", ".join(ctx.get("labels", [])) or "None"}

### Description
{description[:1000]}{"..." if len(description) > 1000 else ""}
"""

            # Add parent context if available
            parent = ctx.get("parent")
            if parent:
                part += f"""
### Parent Epic: {parent.get("key")}
{parent.get("summary", "N/A")}
"""

            context_parts.append(part)

        if context_parts:
            return "---\n# Jira Context (Auto-fetched)\n\n" + "\n---\n".join(context_parts)

        return ""


class EntityExtractionNode:
    """
    LangGraph node that extracts and hydrates Jira entities from user input.

    This node runs early in the pipeline to enrich context before
    intent classification and processing.
    """

    def __init__(self, jira_service: Any = None):
        self.extractor = EntityExtractor()
        self.hydrator = ContextHydrator(jira_service=jira_service)

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Extract and hydrate entities from user input.

        Args:
            state: Current agent state

        Returns:
            State update with extracted_entities and enriched_context
        """
        # Get user input from various possible sources
        user_input = state.get("epic_input") or ""
        logger.info(f"EntityExtractionNode: epic_input={user_input[:100] if user_input else 'EMPTY'!r}")

        if not user_input:
            messages = state.get("messages", [])
            logger.info(f"EntityExtractionNode: Checking messages, count={len(messages)}")
            for msg in reversed(messages):
                if msg.get("role") in ["user", "human"]:
                    user_input = msg.get("content", "")
                    logger.info(f"EntityExtractionNode: Found user message={user_input[:100]!r}")
                    break

        if not user_input:
            logger.warning("EntityExtractionNode: No user input found in epic_input or messages!")
            return {
                "extracted_entities": [],
                "enriched_context": "",
                "stories": state.get("stories", []),  # Preserve stories
            }

        # Extract entities
        entities = self.extractor.extract(user_input)

        if not entities:
            logger.info("EntityExtractionNode: No entities found in input")
            return {
                "extracted_entities": [],
                "enriched_context": "",
                "stories": state.get("stories", []),  # Preserve stories
            }

        # Hydrate entities with Jira context
        entities = await self.hydrator.hydrate_entities(
            entities,
            include_parent=True,
            include_children=False,
        )

        # Format context for prompt
        enriched_context = self.hydrator.format_context_for_prompt(entities)

        # Determine auto-bound project/epic from entities
        auto_bound_project = None
        auto_bound_epic = None

        for entity in entities:
            if entity.hydrated_context:
                # Extract project from issue key
                if not auto_bound_project and entity.entity_type == "issue":
                    auto_bound_project = entity.key.split("-")[0]

                # Check if this is an epic or has a parent epic
                if not auto_bound_epic:
                    if entity.hydrated_context.get("issuetype") == "Epic":
                        auto_bound_epic = entity.key
                    elif entity.hydrated_context.get("parent"):
                        auto_bound_epic = entity.hydrated_context["parent"].get("key")

        logger.info(
            f"EntityExtractionNode: Extracted {len(entities)} entities, "
            f"auto_project={auto_bound_project}, auto_epic={auto_bound_epic}"
        )

        # Preserve stories through the node chain
        existing_stories = state.get("stories", [])
        logger.info(f"EntityExtractionNode: Preserving {len(existing_stories)} stories")

        return {
            "extracted_entities": [e.to_dict() for e in entities],
            "enriched_context": enriched_context,
            "auto_bound_project": auto_bound_project,
            "auto_bound_epic": auto_bound_epic,
            "stories": existing_stories,  # Explicitly preserve stories
        }
