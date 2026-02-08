"""
Unit Tests for Multi-Intent Architecture Nodes
==============================================
Tests for IntentNode, StoryEnhanceNode, GroomNode, and EntityExtractionNode.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the modules under test
from src.app.agents.backlog.intents import UserIntent, INTENT_DESCRIPTIONS, get_intent_classification_prompt
from src.app.agents.backlog.nodes.entity_extraction_node import (
    EntityExtractor,
    ExtractedEntity,
    ContextHydrator,
)
from src.app.agents.backlog.nodes.story_enhance_node import (
    StoryEnhanceNode,
    EnhancementType,
    detect_story_reference,
    detect_enhancement_type,
)
from src.app.agents.backlog.nodes.groom_node import (
    GroomNode,
    BacklogAnalyzer,
    GroomingReport,
    DuplicatePair,
    QualityIssue,
)
from src.app.agents.backlog.schemas import UserStory, AcceptanceCriteria
from src.app.agents.backlog.config import BacklogAgentConfig


# =============================================================================
# Tests for UserIntent Enum
# =============================================================================

class TestUserIntent:
    """Tests for UserIntent enum and related functions."""
    
    def test_all_intents_have_descriptions(self):
        """Ensure all intents have descriptions for classification."""
        for intent in UserIntent:
            if intent not in (UserIntent.UNKNOWN, UserIntent.ESTIMATE):
                assert intent in INTENT_DESCRIPTIONS, f"Missing description for {intent}"
    
    def test_intent_values_are_lowercase(self):
        """Ensure intent values are lowercase for consistent routing."""
        for intent in UserIntent:
            assert intent.value == intent.value.lower(), f"Intent {intent} should be lowercase"
    
    def test_get_intent_classification_prompt(self):
        """Test that classification prompt includes all intents."""
        prompt = get_intent_classification_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be a substantial prompt
        assert "decompose" in prompt.lower()
        assert "refine" in prompt.lower()


# =============================================================================
# Tests for EntityExtractor
# =============================================================================

class TestEntityExtractor:
    """Tests for Jira entity extraction from user messages."""
    
    def setup_method(self):
        self.extractor = EntityExtractor()
    
    def test_extract_single_issue_key(self):
        """Extract a single Jira issue key."""
        entities = self.extractor.extract("Please decompose KAN-123")
        
        assert len(entities) == 1
        assert entities[0].entity_type == "issue"
        assert entities[0].key == "KAN-123"
        assert entities[0].confidence == 1.0
    
    def test_extract_multiple_issue_keys(self):
        """Extract multiple Jira issue keys from a message."""
        entities = self.extractor.extract(
            "Consider KAN-45 and also reference KAN-12 for constraints"
        )
        
        assert len(entities) == 2
        keys = {e.key for e in entities}
        assert keys == {"KAN-45", "KAN-12"}
    
    def test_no_duplicate_extraction(self):
        """Same issue key mentioned twice should only be extracted once."""
        entities = self.extractor.extract(
            "Look at KAN-123, then update KAN-123 with new details"
        )
        
        assert len(entities) == 1
        assert entities[0].key == "KAN-123"
    
    def test_extract_primary_issue(self):
        """Extract the primary (first) issue from text."""
        primary = self.extractor.extract_primary_issue(
            "Decompose KAN-45 based on KAN-12 constraints"
        )
        
        assert primary is not None
        assert primary.key == "KAN-45"
    
    def test_no_issues_in_text(self):
        """Handle text with no Jira keys gracefully."""
        entities = self.extractor.extract("Add user authentication feature")
        
        assert len(entities) == 0
    
    def test_various_project_keys(self):
        """Extract issues with different project key formats."""
        entities = self.extractor.extract(
            "Check ABC-1, PROJECT-999, and XY-42"
        )
        
        assert len(entities) == 3
        keys = {e.key for e in entities}
        assert "ABC-1" in keys
        assert "PROJECT-999" in keys
        assert "XY-42" in keys


# =============================================================================
# Tests for Story Detection
# =============================================================================

class TestStoryDetection:
    """Tests for story reference detection in user messages."""
    
    def setup_method(self):
        self.stories = [
            UserStory(
                id="STORY-001",
                title="Setup Authentication",
                description="As a user, I want to log in",
                acceptance_criteria=[],
            ),
            UserStory(
                id="STORY-002",
                title="Implement Login Form",
                description="As a user, I want a login form",
                acceptance_criteria=[],
            ),
            UserStory(
                id="STORY-003",
                title="Add Password Reset",
                description="As a user, I want to reset my password",
                acceptance_criteria=[],
            ),
        ]
    
    def test_detect_by_story_number(self):
        """Detect story by 'story 1' format."""
        story = detect_story_reference("Add edge cases to story 1", self.stories)
        
        assert story is not None
        assert story.id == "STORY-001"
    
    def test_detect_by_hash_number(self):
        """Detect story by '#2' format."""
        story = detect_story_reference("Enhance #2 with BDD scenarios", self.stories)
        
        assert story is not None
        assert story.id == "STORY-002"
    
    def test_detect_by_ordinal(self):
        """Detect story by 'first story' format."""
        story = detect_story_reference("Improve the first story", self.stories)
        
        assert story is not None
        assert story.id == "STORY-001"
    
    def test_detect_second_story_ordinal(self):
        """Detect story by 'second story' format."""
        story = detect_story_reference("Add ACs to the second story", self.stories)
        
        assert story is not None
        assert story.id == "STORY-002"
    
    def test_no_story_reference(self):
        """Handle message with no story reference."""
        story = detect_story_reference("Add more details", self.stories)
        
        assert story is None


# =============================================================================
# Tests for Enhancement Type Detection
# =============================================================================

class TestEnhancementTypeDetection:
    """Tests for enhancement type detection from user messages."""
    
    def test_detect_acceptance_criteria(self):
        """Detect acceptance criteria enhancement request."""
        assert detect_enhancement_type("Add acceptance criteria") == EnhancementType.ACCEPTANCE_CRITERIA
        assert detect_enhancement_type("more AC needed") == EnhancementType.ACCEPTANCE_CRITERIA
    
    def test_detect_edge_cases(self):
        """Detect edge case enhancement request."""
        assert detect_enhancement_type("Add edge cases") == EnhancementType.EDGE_CASES
        assert detect_enhancement_type("handle error scenarios") == EnhancementType.EDGE_CASES
    
    def test_detect_bdd(self):
        """Detect BDD scenario enhancement request."""
        assert detect_enhancement_type("Add BDD scenarios") == EnhancementType.BDD_SCENARIOS
        assert detect_enhancement_type("given when then format") == EnhancementType.BDD_SCENARIOS
    
    def test_detect_technical_notes(self):
        """Detect technical notes enhancement request."""
        assert detect_enhancement_type("Add technical notes") == EnhancementType.TECHNICAL_NOTES
        assert detect_enhancement_type("implementation details") == EnhancementType.TECHNICAL_NOTES
    
    def test_default_to_full(self):
        """Default to full enhancement when type unclear."""
        assert detect_enhancement_type("improve this story") == EnhancementType.FULL


# =============================================================================
# Tests for BacklogAnalyzer
# =============================================================================

class TestBacklogAnalyzer:
    """Tests for backlog analysis functionality."""
    
    def setup_method(self):
        self.config = BacklogAgentConfig(USE_MOCKS=True)
        self.analyzer = BacklogAnalyzer(config=self.config)
        
        self.sample_stories = [
            UserStory(
                id="STORY-001",
                title="Setup project infrastructure",
                description="As a developer, I want the project structure in place",
                acceptance_criteria=[
                    AcceptanceCriteria(description="Project is created"),
                ],
                estimated_complexity="S",
            ),
            UserStory(
                id="STORY-002",
                title="Implement user authentication",
                description="As a user, I want to log in to the system",
                acceptance_criteria=[
                    AcceptanceCriteria(description="User can log in"),
                    AcceptanceCriteria(description="User can log out"),
                ],
                dependencies=["STORY-001"],
                estimated_complexity="M",
            ),
            UserStory(
                id="STORY-003",
                title="Test user login functionality",  
                description="As a tester, I want to verify login works correctly",
                acceptance_criteria=[],  # Missing ACs - quality issue
            ),
        ]
    
    def test_analyze_returns_report(self):
        """Analyze should return a GroomingReport."""
        report = self.analyzer.analyze(self.sample_stories)
        
        assert isinstance(report, GroomingReport)
        assert report.total_stories == 3
    
    def test_detect_missing_acceptance_criteria(self):
        """Detect stories missing acceptance criteria."""
        report = self.analyzer.analyze(self.sample_stories)
        
        # STORY-003 has no ACs
        high_issues = [q for q in report.quality_issues if q.severity == "high"]
        story_ids = {q.story_id for q in high_issues}
        
        assert "STORY-003" in story_ids
    
    def test_detect_explicit_dependencies(self):
        """Detect explicitly declared dependencies."""
        report = self.analyzer.analyze(self.sample_stories)
        
        explicit_deps = [d for d in report.dependencies if "Explicit" in d.reason]
        
        assert len(explicit_deps) >= 1
        assert any(d.story_id == "STORY-002" and d.depends_on == "STORY-001" for d in explicit_deps)
    
    def test_infer_dependencies(self):
        """Infer dependencies based on story content."""
        report = self.analyzer.analyze(self.sample_stories)
        
        # Testing stories should depend on implementation stories
        inferred_deps = [d for d in report.dependencies if "Inferred" in d.reason]
        
        # STORY-003 (test) should depend on STORY-002 (implement)
        assert any(d.story_id == "STORY-003" for d in inferred_deps)
    
    def test_generate_summary(self):
        """Summary should describe the analysis results."""
        report = self.analyzer.analyze(self.sample_stories)
        
        assert report.summary is not None
        assert "Analyzed" in report.summary
        assert "3" in report.summary  # 3 stories
    
    def test_report_to_dict(self):
        """Report should convert to dict for JSON serialization."""
        report = self.analyzer.analyze(self.sample_stories)
        report_dict = report.to_dict()
        
        assert isinstance(report_dict, dict)
        assert "total_stories" in report_dict
        assert "duplicates" in report_dict
        assert "dependencies" in report_dict
        assert "quality_issues" in report_dict


# =============================================================================
# Tests for StoryEnhanceNode (Mock Mode)
# =============================================================================

class TestStoryEnhanceNodeMock:
    """Tests for StoryEnhanceNode in mock mode."""
    
    def setup_method(self):
        self.config = BacklogAgentConfig(USE_MOCKS=True)
        self.node = StoryEnhanceNode(config=self.config)
        
        self.sample_story = UserStory(
            id="STORY-001",
            title="User Authentication",
            description="As a user, I want to log in",
            acceptance_criteria=[
                AcceptanceCriteria(description="User can enter credentials"),
            ],
            edge_cases=[],
            technical_notes=[],
        )
    
    @pytest.mark.asyncio
    async def test_enhance_edge_cases_mock(self):
        """Mock enhance should add edge cases."""
        enhanced = await self.node._mock_enhance(
            self.sample_story,
            EnhancementType.EDGE_CASES,
            "Add edge cases"
        )
        
        assert len(enhanced.edge_cases) > len(self.sample_story.edge_cases)
    
    @pytest.mark.asyncio
    async def test_enhance_acceptance_criteria_mock(self):
        """Mock enhance should add acceptance criteria."""
        enhanced = await self.node._mock_enhance(
            self.sample_story,
            EnhancementType.ACCEPTANCE_CRITERIA,
            "Add more AC"
        )
        
        assert len(enhanced.acceptance_criteria) > len(self.sample_story.acceptance_criteria)
    
    @pytest.mark.asyncio
    async def test_enhance_technical_notes_mock(self):
        """Mock enhance should add technical notes."""
        enhanced = await self.node._mock_enhance(
            self.sample_story,
            EnhancementType.TECHNICAL_NOTES,
            "Add tech notes"
        )
        
        assert len(enhanced.technical_notes) > len(self.sample_story.technical_notes)
    
    @pytest.mark.asyncio
    async def test_node_requires_stories(self):
        """Node should error when no stories exist."""
        state = {"stories": [], "refinement_feedback": "Add edge cases to story 1"}
        
        result = await self.node(state)
        
        assert "error" in result
        assert "no stories" in result["error"].lower()


# =============================================================================
# Tests for GroomNode (Mock Mode)
# =============================================================================

class TestGroomNodeMock:
    """Tests for GroomNode functionality."""
    
    def setup_method(self):
        self.config = BacklogAgentConfig(USE_MOCKS=True)
        self.node = GroomNode(config=self.config)
    
    @pytest.mark.asyncio
    async def test_groom_requires_stories(self):
        """Groom should handle empty story list gracefully."""
        state = {"stories": []}
        
        result = await self.node(state)
        
        # Should return help response instead of error
        assert "help_response" in result or "grooming_report" in result
    
    @pytest.mark.asyncio
    async def test_groom_analyzes_stories(self):
        """Groom should analyze provided stories."""
        stories = [
            {
                "id": "STORY-001",
                "title": "Setup",
                "description": "Setup project",
                "acceptance_criteria": [],
            },
            {
                "id": "STORY-002", 
                "title": "Implement",
                "description": "Implement feature",
                "acceptance_criteria": [{"description": "Feature works"}],
            },
        ]
        
        state = {"stories": stories}
        
        result = await self.node(state)
        
        assert "grooming_report" in result
        assert result["grooming_report"] is not None


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
