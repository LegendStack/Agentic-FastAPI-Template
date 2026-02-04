"""
Backlog Assistant Agent Tests
=============================
Unit tests for the Story Decomposition Agent.
"""

import pytest

from src.app.agents.backlog import (
    BacklogAgentConfig,
    BacklogAssistantAgent,
    AcceptanceCriteria,
    DecompositionResult,
    Epic,
    UserStory,
)
from src.app.agents.backlog.nodes import (
    DecomposeNode,
    FormatNode,
    InputNode,
    RefineNode,
)
from src.app.agents.backlog.state import BacklogAgentState


# === Schema Tests ===


class TestSchemas:
    """Test Pydantic schema models."""

    def test_acceptance_criteria_basic(self):
        """Test basic acceptance criteria creation."""
        ac = AcceptanceCriteria(description="User can click the button")
        assert ac.description == "User can click the button"
        assert ac.given is None
        assert ac.is_edge_case is False

    def test_acceptance_criteria_bdd(self):
        """Test BDD-style acceptance criteria."""
        ac = AcceptanceCriteria(
            description="Login redirect",
            given="the user is authenticated",
            when="they visit the dashboard",
            then="they see their profile",
        )
        bdd_string = ac.to_bdd_string()
        assert "Given" in bdd_string
        assert "When" in bdd_string
        assert "Then" in bdd_string

    def test_user_story_creation(self):
        """Test user story creation with all fields."""
        story = UserStory(
            id="STORY-001",
            title="Test Story",
            description="As a user, I want to test, so that I validate.",
            acceptance_criteria=[
                AcceptanceCriteria(description="Test passes"),
            ],
            estimated_complexity="M",
            tags=["testing"],
        )
        assert story.id == "STORY-001"
        assert story.estimated_complexity == "M"
        assert len(story.acceptance_criteria) == 1

    def test_user_story_to_markdown(self):
        """Test markdown conversion."""
        story = UserStory(
            id="STORY-001",
            title="Test Story",
            description="As a user, I want to test.",
            acceptance_criteria=[
                AcceptanceCriteria(description="Works correctly"),
            ],
            edge_cases=["Handle errors"],
            estimated_complexity="S",
        )
        md = story.to_markdown()
        assert "### STORY-001" in md
        assert "**Complexity:** S" in md
        assert "Works correctly" in md
        assert "Edge Cases" in md

    def test_user_story_to_jira_format(self):
        """Test JIRA format conversion."""
        story = UserStory(
            id="STORY-001",
            title="Test Story",
            description="As a user, I want to test.",
            acceptance_criteria=[
                AcceptanceCriteria(description="Works correctly"),
            ],
            tags=["backend"],
        )
        jira = story.to_jira_format()
        assert jira["summary"] == "Test Story"
        assert "Acceptance Criteria" in jira["description"]
        assert "backend" in jira["labels"]

    def test_decomposition_result_get_dependency_order(self):
        """Test dependency ordering of stories."""
        result = DecompositionResult(
            epic=Epic(title="Test", description="Test epic"),
            stories=[
                UserStory(
                    id="STORY-003",
                    title="Third",
                    description="This story depends on first story",
                    dependencies=["STORY-001"],
                ),
                UserStory(
                    id="STORY-001",
                    title="First",
                    description="No dependencies needed for this story",
                ),
                UserStory(
                    id="STORY-002",
                    title="Second",
                    description="This story depends on the third story",
                    dependencies=["STORY-003"],
                ),
            ],
            summary="Test result",
        )
        order = result.get_dependency_order()
        # STORY-001 should come first (no deps), then STORY-003, then STORY-002
        assert order.index("STORY-001") < order.index("STORY-003")
        assert order.index("STORY-003") < order.index("STORY-002")


# === Config Tests ===


class TestConfig:
    """Test agent configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BacklogAgentConfig()
        assert config.USE_MOCKS is True
        assert config.STORY_TEMPLATE == "standard"
        assert config.MAX_STORIES_PER_EPIC == 10

    def test_custom_config(self):
        """Test custom configuration."""
        config = BacklogAgentConfig(
            USE_MOCKS=False,
            STORY_TEMPLATE="bdd",
            ENABLE_EDGE_CASES=False,
        )
        assert config.USE_MOCKS is False
        assert config.STORY_TEMPLATE == "bdd"
        assert config.ENABLE_EDGE_CASES is False

    def test_get_enabled_features(self):
        """Test feature list generation."""
        config = BacklogAgentConfig(
            ENABLE_EDGE_CASES=True,
            ENABLE_TECH_TASKS=True,
            ENABLE_JIRA_EXPORT=False,
        )
        features = config.get_enabled_features()
        assert "edge_cases" in features
        assert "tech_tasks" in features
        assert "jira_export" not in features

    def test_get_story_template_description(self):
        """Test template description."""
        config = BacklogAgentConfig(STORY_TEMPLATE="bdd")
        desc = config.get_story_template_description()
        assert "Given-When-Then" in desc


# === Node Tests ===


class TestInputNode:
    """Test input parsing node."""

    @pytest.mark.asyncio
    async def test_parse_simple_epic(self):
        """Test parsing a simple epic description."""
        node = InputNode()
        state: BacklogAgentState = {
            "messages": [{"role": "user", "content": "Add SSO login support for enterprise"}],
            "epic_input": "",
            "parsed_epic": None,
            "stories": [],
            "current_result": None,
            "refinement_feedback": None,
            "is_first_message": True,
            "output_format": "json",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }
        result = await node(state)
        assert result.get("error") is None
        assert result.get("parsed_epic") is not None
        assert result.get("is_first_message") is True

    @pytest.mark.asyncio
    async def test_detect_refinement(self):
        """Test detection of refinement request."""
        node = InputNode()
        state: BacklogAgentState = {
            "messages": [{"role": "user", "content": "Add more edge cases"}],
            "epic_input": "Original epic",
            "parsed_epic": Epic(title="Test", description="Test epic"),
            "stories": [
                UserStory(
                    id="STORY-001",
                    title="Test",
                    description="Test story description here",
                    acceptance_criteria=[],
                )
            ],
            "current_result": None,
            "refinement_feedback": None,
            "is_first_message": False,
            "output_format": "json",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }
        result = await node(state)
        assert result.get("refinement_feedback") == "Add more edge cases"
        assert result.get("is_first_message") is False

    @pytest.mark.asyncio
    async def test_reject_short_input(self):
        """Test rejection of too-short input."""
        node = InputNode()
        state: BacklogAgentState = {
            "messages": [{"role": "user", "content": "Hi"}],
            "epic_input": "",
            "parsed_epic": None,
            "stories": [],
            "current_result": None,
            "refinement_feedback": None,
            "is_first_message": True,
            "output_format": "json",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }
        result = await node(state)
        assert result.get("error") is not None
        assert "too short" in result["error"].lower()


class TestDecomposeNode:
    """Test story decomposition node."""

    @pytest.mark.asyncio
    async def test_mock_decomposition(self):
        """Test decomposition with mocks."""
        config = BacklogAgentConfig(USE_MOCKS=True)
        node = DecomposeNode(config=config)

        epic = Epic(
            title="SSO Login",
            description="Add SSO login support for enterprise customers",
        )

        state: BacklogAgentState = {
            "messages": [],
            "epic_input": epic.description,
            "parsed_epic": epic,
            "stories": [],
            "current_result": None,
            "refinement_feedback": None,
            "is_first_message": True,
            "output_format": "json",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }

        result = await node(state)
        assert result.get("error") is None
        assert len(result.get("stories", [])) >= 2
        assert result.get("current_result") is not None


class TestRefineNode:
    """Test story refinement node."""

    @pytest.mark.asyncio
    async def test_mock_add_edge_cases(self):
        """Test adding edge cases via refinement."""
        config = BacklogAgentConfig(USE_MOCKS=True)
        node = RefineNode(config=config)

        current_result = DecompositionResult(
            epic=Epic(title="Test", description="Test epic"),
            stories=[
                UserStory(
                    id="STORY-001",
                    title="Test Story",
                    description="Test description",
                    acceptance_criteria=[],
                    edge_cases=[],
                )
            ],
            summary="Test decomposition",
        )

        state: BacklogAgentState = {
            "messages": [],
            "epic_input": "",
            "parsed_epic": current_result.epic,
            "stories": current_result.stories,
            "current_result": current_result,
            "refinement_feedback": "Add more edge cases",
            "is_first_message": False,
            "output_format": "json",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }

        result = await node(state)
        assert result.get("error") is None
        # Mock should have added edge cases
        stories = result.get("stories", [])
        assert len(stories) >= 1


class TestFormatNode:
    """Test output formatting node."""

    @pytest.mark.asyncio
    async def test_format_json(self):
        """Test JSON formatting."""
        node = FormatNode()

        current_result = DecompositionResult(
            epic=Epic(title="Test", description="Test epic"),
            stories=[
                UserStory(
                    id="STORY-001",
                    title="Test",
                    description="Test story for formatting",
                    acceptance_criteria=[],
                )
            ],
            summary="Test",
        )

        state: BacklogAgentState = {
            "messages": [],
            "epic_input": "",
            "parsed_epic": current_result.epic,
            "stories": current_result.stories,
            "current_result": current_result,
            "refinement_feedback": None,
            "is_first_message": False,
            "output_format": "json",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }

        result = await node(state)
        assert result.get("error") is None
        assert result.get("formatted_output") is not None
        assert "STORY-001" in result["formatted_output"]

    @pytest.mark.asyncio
    async def test_format_markdown(self):
        """Test Markdown formatting."""
        config = BacklogAgentConfig(DEFAULT_OUTPUT_FORMAT="markdown")
        node = FormatNode(config=config)

        current_result = DecompositionResult(
            epic=Epic(title="Test Epic", description="Test epic"),
            stories=[
                UserStory(
                    id="STORY-001",
                    title="Test Story",
                    description="Test description",
                    acceptance_criteria=[
                        AcceptanceCriteria(description="Works"),
                    ],
                )
            ],
            summary="Test",
        )

        state: BacklogAgentState = {
            "messages": [],
            "epic_input": "",
            "parsed_epic": current_result.epic,
            "stories": current_result.stories,
            "current_result": current_result,
            "refinement_feedback": None,
            "is_first_message": False,
            "output_format": "markdown",
            "formatted_output": None,
            "export_result": None,
            "thread_id": "test-123",
            "tenant_id": None,
            "error": None,
            "metadata": {},
        }

        result = await node(state)
        assert result.get("error") is None
        output = result.get("formatted_output", "")
        assert "# Test Epic" in output
        assert "### STORY-001" in output


# === Agent Tests ===


class TestBacklogAssistantAgent:
    """Test the main agent class."""

    @pytest.mark.asyncio
    async def test_decompose_simple_epic(self):
        """Test basic epic decomposition."""
        agent = BacklogAssistantAgent()

        result = await agent.decompose(
            "Add user authentication with email and password"
        )

        assert result.get("error") is None
        assert result.get("thread_id") is not None
        assert result.get("story_count", 0) >= 2
        assert len(result.get("stories", [])) >= 2

    @pytest.mark.asyncio
    async def test_get_config_summary(self):
        """Test configuration summary."""
        config = BacklogAgentConfig(
            STORY_TEMPLATE="bdd",
            ENABLE_EDGE_CASES=True,
        )
        agent = BacklogAssistantAgent(config=config)

        summary = agent.get_config_summary()

        assert summary["story_template"] == "bdd"
        assert "edge_cases" in summary["enabled_features"]
        assert summary["using_mocks"] is True

    @pytest.mark.asyncio
    async def test_decompose_with_context(self):
        """Test decomposition with additional context."""
        agent = BacklogAssistantAgent()

        result = await agent.decompose(
            epic_description="Add SSO login",
            context="We use Azure AD. Need SAML support.",
            output_format="json",
        )

        assert result.get("error") is None
        assert result.get("story_count", 0) >= 2


# === Integration Tests ===


class TestIntegration:
    """Integration tests for the full workflow."""

    @pytest.mark.asyncio
    async def test_decompose_and_get_markdown(self):
        """Test decomposition with markdown output."""
        agent = BacklogAssistantAgent()

        result = await agent.decompose(
            "Build a REST API for user management",
            output_format="markdown",
        )

        assert result.get("error") is None
        formatted = result.get("formatted_output", "")
        assert "#" in formatted  # Has markdown headers
        assert "STORY-" in formatted  # Has story IDs



class TestRefinementFlow:
    """Test the 'Dumb UI / Smart Agent' refinement flow."""

    @pytest.mark.asyncio
    async def test_hydration_flow(self):
        """Test starting the agent with pre-populated stories (Hydration)."""
        agent = BacklogAssistantAgent()

        # Door B: Start with existing stories
        existing_stories = [
            UserStory(
                id="OLD-01",
                title="Existing Story",
                description="This already exists",
                acceptance_criteria=[],
            )
        ]

        # User message for refinement
        message = "Add a technical note about database migrations"

        result = await agent.chat(
            thread_id="test-hydration", message=message, initial_stories=existing_stories
        )

        assert result.get("error") is None
        assert result.get("metadata", {}).get("is_refinement") is True
        # Since RefineNode in mock mode (default) returns updated stories
        assert len(result.get("stories", [])) > 0

        # Verify the RefineNode was hit (in mock mode it adds recommendations/notes)
        assert result.get("response", {}).get("recommendations") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
