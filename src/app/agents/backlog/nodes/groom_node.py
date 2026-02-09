"""
Backlog Grooming Node
=====================
Analyzes the current backlog for quality issues, duplicates,
dependencies, and provides prioritization recommendations.
"""

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from ...azure_openai import LLMService
from ..config import BacklogAgentConfig
from ..schemas import UserStory
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


@dataclass
class DuplicatePair:
    """Represents a pair of potentially duplicate stories."""

    story_id_1: str
    story_id_2: str
    similarity_score: float
    reason: str


@dataclass
class DependencyInfo:
    """Represents a dependency between stories."""

    story_id: str
    depends_on: str
    relationship_type: str  # "blocks", "requires", "relates_to"
    reason: str


@dataclass
class QualityIssue:
    """Represents a quality issue in a story."""

    story_id: str
    issue_type: str  # "missing_ac", "missing_edge_cases", "vague_description", etc.
    severity: str  # "low", "medium", "high"
    suggestion: str


@dataclass
class PrioritySuggestion:
    """Represents a prioritization suggestion."""

    story_id: str
    current_priority: int | None
    suggested_priority: int
    reason: str


@dataclass
class GroomingReport:
    """Complete grooming analysis report."""

    total_stories: int
    duplicates: list[DuplicatePair] = field(default_factory=list)
    dependencies: list[DependencyInfo] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)
    priority_suggestions: list[PrioritySuggestion] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "total_stories": self.total_stories,
            "duplicates": [
                {"story_1": d.story_id_1, "story_2": d.story_id_2, "similarity": d.similarity_score, "reason": d.reason}
                for d in self.duplicates
            ],
            "dependencies": [
                {"story": d.story_id, "depends_on": d.depends_on, "type": d.relationship_type, "reason": d.reason}
                for d in self.dependencies
            ],
            "quality_issues": [
                {"story": q.story_id, "issue": q.issue_type, "severity": q.severity, "suggestion": q.suggestion}
                for q in self.quality_issues
            ],
            "priority_suggestions": [
                {
                    "story": p.story_id,
                    "current": p.current_priority,
                    "suggested": p.suggested_priority,
                    "reason": p.reason,
                }
                for p in self.priority_suggestions
            ],
            "summary": self.summary,
        }


class BacklogAnalyzer:
    """
    Analyzes backlog for quality issues, duplicates, and dependencies.
    """

    def __init__(self, config: BacklogAgentConfig | None = None):
        self.config = config or BacklogAgentConfig()
        self.similarity_threshold = 0.7  # Threshold for duplicate detection

    def analyze(self, stories: list[UserStory]) -> GroomingReport:
        """
        Perform full backlog analysis.

        Args:
            stories: List of stories to analyze

        Returns:
            Complete grooming report
        """
        report = GroomingReport(total_stories=len(stories))

        # Run all analyses
        report.duplicates = self._find_duplicates(stories)
        report.dependencies = self._analyze_dependencies(stories)
        report.quality_issues = self._check_quality(stories)
        report.priority_suggestions = self._suggest_priorities(stories)
        report.summary = self._generate_summary(report)

        return report

    def _find_duplicates(self, stories: list[UserStory]) -> list[DuplicatePair]:
        """Find potentially duplicate stories using multiple similarity signals."""
        duplicates = []
        # Lower threshold to catch more potential issues (better to flag than miss)
        threshold = 0.60 

        for i, story1 in enumerate(stories):
            for story2 in stories[i + 1 :]:
                # 1. Title Sequence Similarity (Order matters)
                title_seq = SequenceMatcher(None, story1.title.lower(), story2.title.lower()).ratio()

                # 2. Title Jaccard Similarity (Token overlap, order doesn't matter)
                s1_tokens = set(story1.title.lower().split())
                s2_tokens = set(story2.title.lower().split())
                intersection = len(s1_tokens.intersection(s2_tokens))
                union = len(s1_tokens.union(s2_tokens))
                title_jaccard = intersection / union if union else 0.0

                # 3. Description Sequence Similarity
                desc_seq = SequenceMatcher(
                    None, (story1.description or "").lower(), (story2.description or "").lower()
                ).ratio()

                # Take the strongest signal, but dampen if description is totally different
                # If titles are identical (1.0), it's a dupe.
                # If descriptions are identical (1.0), it's a dupe.
                # If somewhat similar in both, it's a dupe.
                
                # We use a weighted mix, but allow strong individual signals to boost it
                max_title = max(title_seq, title_jaccard)
                
                # Logic: If titles are very similar (>0.8), or desc is very similar (>0.8), or both are moderately similar
                is_duplicate = False
                reason = ""
                score = 0.0

                if max_title > 0.8:
                    is_duplicate = True
                    score = max_title
                    reason = f"Titles are very similar ({int(score*100)}%)"
                elif desc_seq > 0.85: # Higher threshold for description as they can be boilerplate
                    is_duplicate = True
                    score = desc_seq
                    reason = f"Descriptions are very similar ({int(score*100)}%)"
                else:
                    # Combined score
                    combined = (max_title * 0.5) + (desc_seq * 0.5)
                    if combined > threshold:
                        is_duplicate = True
                        score = combined
                        reason = f"Combined similarity detected ({int(score*100)}%)"

                if is_duplicate:
                    duplicates.append(
                        DuplicatePair(
                            story_id_1=story1.id,
                            story_id_2=story2.id,
                            similarity_score=round(score, 2),
                            reason=reason,
                        )
                    )

        return duplicates

    def _analyze_dependencies(self, stories: list[UserStory]) -> list[DependencyInfo]:
        """Analyze and infer dependencies between stories."""
        dependencies = []

        # Check explicit dependencies
        for story in stories:
            if story.dependencies:
                for dep in story.dependencies:
                    dependencies.append(
                        DependencyInfo(
                            story_id=story.id,
                            depends_on=dep,
                            relationship_type="requires",
                            reason="Explicitly declared dependency",
                        )
                    )

        # Infer implicit dependencies based on keywords
        setup_keywords = ["setup", "configure", "initialize", "create", "bootstrap"]
        impl_keywords = ["implement", "add", "build", "develop"]
        test_keywords = ["test", "verify", "validate", "qa"]

        # Find setup stories (likely should be done first)
        setup_stories = [s for s in stories if any(kw in s.title.lower() for kw in setup_keywords)]
        impl_stories = [s for s in stories if any(kw in s.title.lower() for kw in impl_keywords)]
        test_stories = [s for s in stories if any(kw in s.title.lower() for kw in test_keywords)]

        # Infer: implementation depends on setup
        for impl in impl_stories:
            for setup in setup_stories:
                if setup.id != impl.id and not self._has_dependency(dependencies, impl.id, setup.id):
                    dependencies.append(
                        DependencyInfo(
                            story_id=impl.id,
                            depends_on=setup.id,
                            relationship_type="blocks",
                            reason="Inferred: Implementation likely requires setup to be completed first",
                        )
                    )

        # Infer: testing depends on implementation
        for test in test_stories:
            for impl in impl_stories:
                if test.id != impl.id and not self._has_dependency(dependencies, test.id, impl.id):
                    dependencies.append(
                        DependencyInfo(
                            story_id=test.id,
                            depends_on=impl.id,
                            relationship_type="blocks",
                            reason="Inferred: Testing likely requires implementation to be completed first",
                        )
                    )

        return dependencies

    def _has_dependency(self, deps: list[DependencyInfo], story_id: str, depends_on: str) -> bool:
        """Check if a dependency already exists."""
        return any(d.story_id == story_id and d.depends_on == depends_on for d in deps)

    def _check_quality(self, stories: list[UserStory]) -> list[QualityIssue]:
        """Check stories for quality issues."""
        issues = []

        for story in stories:
            # Check for missing or insufficient acceptance criteria
            ac_count = len(story.acceptance_criteria) if story.acceptance_criteria else 0
            if ac_count == 0:
                issues.append(
                    QualityIssue(
                        story_id=story.id,
                        issue_type="missing_acceptance_criteria",
                        severity="high",
                        suggestion="Add at least 2-3 acceptance criteria to clarify expected behavior",
                    )
                )
            elif ac_count < 2:
                issues.append(
                    QualityIssue(
                        story_id=story.id,
                        issue_type="insufficient_acceptance_criteria",
                        severity="medium",
                        suggestion="Consider adding more acceptance criteria for completeness",
                    )
                )

            # Check for missing edge cases
            edge_count = len(story.edge_cases) if story.edge_cases else 0
            if edge_count == 0:
                issues.append(
                    QualityIssue(
                        story_id=story.id,
                        issue_type="missing_edge_cases",
                        severity="medium",
                        suggestion="Add edge cases to handle error scenarios and boundary conditions",
                    )
                )

            # Check for vague descriptions
            if story.description:
                # Too short
                if len(story.description) < 50:
                    issues.append(
                        QualityIssue(
                            story_id=story.id,
                            issue_type="vague_description",
                            severity="medium",
                            suggestion="Expand the description to provide more context and detail",
                        )
                    )

                # Missing user story format
                if not any(kw in story.description.lower() for kw in ["as a", "i want", "so that"]):
                    issues.append(
                        QualityIssue(
                            story_id=story.id,
                            issue_type="non_standard_format",
                            severity="low",
                            suggestion="Consider using 'As a [user], I want [goal], so that [benefit]' format",
                        )
                    )

            # Check for missing complexity estimate
            if not story.estimated_complexity:
                issues.append(
                    QualityIssue(
                        story_id=story.id,
                        issue_type="missing_estimate",
                        severity="low",
                        suggestion="Add a complexity estimate (S/M/L/XL) for planning purposes",
                    )
                )

        return issues

    def _suggest_priorities(self, stories: list[UserStory]) -> list[PrioritySuggestion]:
        """Suggest priority order based on dependencies and value."""
        suggestions = []

        # Calculate a priority score for each story
        story_scores = []
        for story in stories:
            score = 0

            # Higher value = higher priority
            if story.business_value_score:
                score += story.business_value_score
            else:
                score += 50  # Default mid-value

            # Lower effort = higher priority (quick wins)
            if story.effort_score:
                score += (100 - story.effort_score) * 0.5
            else:
                score += 25  # Default mid-effort bonus

            # Setup stories get priority boost
            if any(kw in story.title.lower() for kw in ["setup", "config", "initialize"]):
                score += 30

            # Stories with dependencies go later
            if story.dependencies:
                score -= len(story.dependencies) * 10

            story_scores.append((story, score))

        # Sort by score descending
        story_scores.sort(key=lambda x: x[1], reverse=True)

        # Generate suggestions
        for i, (story, score) in enumerate(story_scores):
            suggested_priority = i + 1
            current_priority = int(story.priority) if story.priority and story.priority.isdigit() else None

            if current_priority is None or abs(current_priority - suggested_priority) > 1:
                suggestions.append(
                    PrioritySuggestion(
                        story_id=story.id,
                        current_priority=current_priority,
                        suggested_priority=suggested_priority,
                        reason=f"Score: {int(score)} - Based on value/effort ratio and dependencies",
                    )
                )

        return suggestions

    def _generate_summary(self, report: GroomingReport) -> str:
        """Generate a summary of the grooming report."""
        parts = [f"Analyzed {report.total_stories} stories in the backlog."]

        if report.duplicates:
            parts.append(f"⚠️ Found {len(report.duplicates)} potential duplicate pairs.")
        else:
            parts.append("✅ No duplicate stories detected.")

        if report.dependencies:
            explicit = sum(1 for d in report.dependencies if "Explicit" in d.reason)
            inferred = len(report.dependencies) - explicit
            parts.append(
                f"🔗 Found {len(report.dependencies)} dependencies ({explicit} explicit, {inferred} inferred)."
            )

        high_issues = sum(1 for q in report.quality_issues if q.severity == "high")
        med_issues = sum(1 for q in report.quality_issues if q.severity == "medium")
        if high_issues or med_issues:
            parts.append(f"📋 Quality check: {high_issues} high-priority, {med_issues} medium-priority issues found.")
        else:
            parts.append("✅ All stories meet quality standards.")

        if report.priority_suggestions:
            parts.append(f"🎯 {len(report.priority_suggestions)} priority reordering suggestions available.")

        return " ".join(parts)


class GroomNode:
    """
    LangGraph node that performs backlog grooming analysis.

    Analyzes the current stories for:
    - Duplicate detection
    - Dependency mapping
    - Quality gaps
    - Prioritization suggestions

    Usage:
        node = GroomNode(config=BacklogAgentConfig())
        updated_state = await node(state)
    """

    def __init__(
        self,
        config: BacklogAgentConfig | None = None,
        llm_service: LLMService | None = None,
    ):
        self.config = config or BacklogAgentConfig()
        self.llm_service = llm_service
        self.analyzer = BacklogAnalyzer(config=config)

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Analyze the backlog and generate a grooming report.

        Args:
            state: Current agent state with stories

        Returns:
            State update with grooming_report
        """
        logger.info("GroomNode: Starting backlog analysis")

        stories = state.get("stories", [])
        if not stories:
            return {
                "grooming_report": None,
                "help_response": "There are no stories to analyze. Please decompose an epic first.",
                "error": None,
            }

        # Convert stories from dicts if needed
        if isinstance(stories[0], dict):
            stories = [UserStory.model_validate(s) for s in stories]

        try:
            # Run analysis
            report = self.analyzer.analyze(stories)

            logger.info(
                f"GroomNode: Analysis complete - "
                f"{len(report.duplicates)} duplicates, "
                f"{len(report.dependencies)} dependencies, "
                f"{len(report.quality_issues)} quality issues"
            )

            return {
                "grooming_report": report.to_dict(),
                "error": None,
            }

        except Exception as e:
            logger.error(f"GroomNode: Error - {e}")
            return {"error": f"Grooming analysis failed: {str(e)}"}


# Convenience function for standalone testing
async def groom_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for GroomNode."""
    node = GroomNode(config=config)
    return await node(state)
