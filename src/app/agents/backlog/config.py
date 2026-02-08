"""
Backlog Agent Configuration
===========================
Feature toggles and settings for the Backlog Assistant Agent.
Each feature can be independently enabled or disabled.
"""

from dataclasses import dataclass, field
from typing import Literal

from ...core.config import settings


@dataclass
class BacklogAgentConfig:
    """
    Configuration for the Backlog Assistant Agent.

    Set USE_MOCKS=True to run without any external LLM dependencies.
    Toggle individual features to customize agent behavior.

    Example:
        config = BacklogAgentConfig(
            USE_MOCKS=False,
            STORY_TEMPLATE="bdd",
            ENABLE_EDGE_CASES=True,
            MAX_STORIES_PER_EPIC=8
        )
        agent = BacklogAssistantAgent(config=config)
    """

    # === Core Settings ===
    USE_MOCKS: bool = field(
        default_factory=lambda: settings.BACKLOG_USE_MOCKS
    )  # Use mock LLM for testing (no API calls)

    # === Output Configuration ===
    DEFAULT_OUTPUT_FORMAT: Literal["json", "markdown", "jira"] = "json"

    # === Story Generation ===
    STORY_TEMPLATE: Literal["standard", "bdd", "minimal"] = "standard"
    MAX_STORIES_PER_EPIC: int = 10  # Limit to prevent runaway generation
    MIN_STORIES_PER_EPIC: int = 2  # Minimum stories for meaningful decomposition

    # === Feature Toggles ===
    ENABLE_EDGE_CASES: bool = True  # Auto-generate edge case scenarios
    ENABLE_TECH_TASKS: bool = True  # Include technical/backend tasks
    ENABLE_DEPENDENCIES: bool = True  # Identify story dependencies
    ENABLE_COMPLEXITY_ESTIMATION: bool = True  # Add T-shirt sizing

    # === Acceptance Criteria ===
    AC_STYLE: Literal["bullet", "bdd", "mixed"] = "bullet"
    MIN_AC_PER_STORY: int = 2
    MAX_AC_PER_STORY: int = 6

    # === JIRA Integration ===
    ENABLE_JIRA_EXPORT: bool = True  # Enable JIRA issue creation
    JIRA_PROJECT_KEY: str | None = None  # Default project for exports
    JIRA_ISSUE_TYPE: str = "Story"  # Issue type for created stories
    JIRA_EPIC_ISSUE_TYPE: str = field(default_factory=lambda: settings.JIRA_EPIC_ISSUE_TYPE)
    JIRA_EPIC_NAME_FIELD: str = field(default_factory=lambda: settings.JIRA_EPIC_NAME_FIELD)
    JIRA_EPIC_LINK_FIELD: str = "customfield_10014"  # Epic link custom field
    JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA: str | None = field(
        default_factory=lambda: settings.JIRA_FIELD_MAP_ACCEPTANCE_CRITERIA
    )
    JIRA_FIELD_MAP_TECH_NOTES: str | None = field(default_factory=lambda: settings.JIRA_FIELD_MAP_TECH_NOTES)
    JIRA_FIELD_MAP_COMPLEXITY: str | None = field(default_factory=lambda: settings.JIRA_FIELD_MAP_COMPLEXITY)
    JIRA_FIELD_MAP_DEPENDENCIES: str | None = field(default_factory=lambda: settings.JIRA_FIELD_MAP_DEPENDENCIES)
    JIRA_FIELD_MAP_PRIORITY: str | None = field(default_factory=lambda: settings.JIRA_FIELD_MAP_PRIORITY)

    # === Refinement ===
    MAX_REFINEMENT_TURNS: int = 10  # Max conversation turns before reset
    ENABLE_AUTO_SUGGESTIONS: bool = True  # Suggest refinements proactively

    # === Quality & Validation ===
    ENABLE_VALIDATION: bool = True  # Validate story structure
    REQUIRE_ACCEPTANCE_CRITERIA: bool = True  # Stories must have AC
    PREVENT_DUPLICATE_DECOMPOSITION: bool = True  # Semantic search for existing epics

    # === Resilience ===
    MAX_RETRIES: int = 3  # LLM retry attempts
    RETRY_DELAY_SECONDS: float = 1.0

    # === Prompt Configuration ===
    SYSTEM_PROMPT_VERSION: int | None = None  # Use specific prompt version
    CUSTOM_PERSONA: str | None = None  # Override default persona

    # === Tags & Labels ===
    DEFAULT_TAGS: list[str] = field(default_factory=list)  # Tags for all stories
    AUTO_TAG_TECHNICAL: bool = True  # Auto-tag technical stories

    def get_story_template_description(self) -> str:
        """Get human-readable description of the story template."""
        templates = {
            "standard": "As a [user], I want [goal], so that [benefit]",
            "bdd": "Given-When-Then format with behavior focus",
            "minimal": "Title and acceptance criteria only",
        }
        return templates.get(self.STORY_TEMPLATE, "Unknown template")

    def get_enabled_features(self) -> list[str]:
        """Get list of enabled feature names for logging/debugging."""
        features = []
        if self.ENABLE_EDGE_CASES:
            features.append("edge_cases")
        if self.ENABLE_TECH_TASKS:
            features.append("tech_tasks")
        if self.ENABLE_DEPENDENCIES:
            features.append("dependencies")
        if self.ENABLE_COMPLEXITY_ESTIMATION:
            features.append("complexity_estimation")
        if self.ENABLE_JIRA_EXPORT:
            features.append("jira_export")
        if self.ENABLE_AUTO_SUGGESTIONS:
            features.append("auto_suggestions")
        return features

    def get_llm(self):
        """
        Get the LLM instance based on mock configuration.

        Returns:
            A mock LLM if USE_MOCKS is True, otherwise the configured LLM.
        """
        if self.USE_MOCKS:
            from ..demo.mocks.mock_llm import MockLLM

            return MockLLM()
        else:
            from langchain_openai import AzureChatOpenAI

            return AzureChatOpenAI(
                azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
                openai_api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value(),
                temperature=0.3,
            )
