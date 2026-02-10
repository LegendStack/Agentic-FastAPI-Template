"""
Backlog Agent Schemas
=====================
Pydantic models for structured LLM output with validation.
These models ensure decomposition results are well-formed and consistent.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AcceptanceCriteria(BaseModel):
    """
    A single acceptance criterion for a user story.

    Supports both bullet-point and BDD (Given/When/Then) styles.

    Examples:
        # Bullet style
        AcceptanceCriteria(description="User can see SSO button on login page")

        # BDD style
        AcceptanceCriteria(
            description="SSO button visibility",
            given="the user is on the login page",
            when="the page loads",
            then="the SSO login button is visible"
        )
    """

    description: str = Field(..., description="Clear, testable criterion")
    given: str | None = Field(None, description="BDD: Initial context/state")
    when: str | None = Field(None, description="BDD: Action or trigger")
    then: str | None = Field(None, description="BDD: Expected outcome")
    is_edge_case: bool = Field(False, description="Whether this is an edge case scenario")

    @model_validator(mode="before")
    @classmethod
    def validate_flexible(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"description": data}
        return data

    def to_bdd_string(self) -> str:
        """Format as BDD string if Given/When/Then are provided."""
        if self.given and self.when and self.then:
            return f"Given {self.given}\nWhen {self.when}\nThen {self.then}"
        return self.description

    def to_bullet_string(self) -> str:
        """Format as bullet point."""
        prefix = "⚠️ " if self.is_edge_case else "✓ "
        return f"{prefix}{self.description}"


class UserStory(BaseModel):
    """
    A decomposed user story with full metadata.

    Follows enterprise patterns with acceptance criteria, dependencies,
    and complexity estimation for sprint planning.

    Example:
        UserStory(
            id="STORY-001",
            title="SSO Login Button",
            description="As a user, I want to see an SSO login button, so that I can authenticate via my company's IdP",
            acceptance_criteria=[...],
            estimated_complexity="M"
        )
    """

    id: str = Field(..., description="Unique story identifier (e.g., STORY-001)")
    title: str = Field(..., description="Short, descriptive title", max_length=100)
    description: str = Field(
        ...,
        description="Full story description in user story format",
        min_length=1,
    )
    acceptance_criteria: list[AcceptanceCriteria] = Field(
        default_factory=list,
        description="Functional requirements defining the 'Definition of Done'.",
    )
    edge_cases: list[str] = Field(
        default_factory=list,
        description="Edge cases and error scenarios to consider",
    )
    technical_notes: list[str] = Field(
        default_factory=list,
        description="Technical implementation notes for developers",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Story IDs this story depends on",
    )
    test_scenarios: list[str] = Field(
        default_factory=list,
        description=(
            "Detailed Gherkin scripts for QA/Automation. Optional: use only for "
            "complex technical validation or scenarios not covered by ACs."
        ),
    )
    estimated_complexity: Literal["XS", "S", "M", "L", "XL"] | None = Field(
        None,
        description="T-shirt size complexity estimate",
    )
    business_value_score: int = Field(
        50,
        ge=1,
        le=100,
        description="Business value score from 1 to 100 (100 = critical/strategic)",
    )
    effort_score: int = Field(
        50,
        ge=1,
        le=100,
        description="Implementation effort score from 1 to 100 (100 = extremely difficult)",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_complexity(cls, data: Any) -> Any:
        if isinstance(data, dict):
            comp = data.get("estimated_complexity")
            if comp and comp not in ["XS", "S", "M", "L", "XL"]:
                data["estimated_complexity"] = None
        return data

    tags: list[str] = Field(
        default_factory=list,
        description="Labels for categorization (e.g., 'frontend', 'security')",
    )
    priority: Literal["must-have", "should-have", "could-have", "won't-have"] | None = Field(
        None,
        description="MoSCoW priority classification",
    )
    is_duplicate: bool = Field(False, description="Whether this story potentially overlaps with an existing one")
    duplicate_reason: str | None = Field(None, description="Explanation for the potential duplicate flag")
    jira_key: str | None = Field(None, description="Associated JIRA issue key")
    jira_url: str | None = Field(None, description="Link to the JIRA issue")

    def to_markdown(self) -> str:
        """Format story as markdown for documentation."""
        lines = [
            f"### {self.id}: {self.title}",
            "",
            f"**Description:** {self.description}",
            "",
        ]

        if self.estimated_complexity:
            lines.append(f"**Complexity:** {self.estimated_complexity}")

        if self.tags:
            lines.append(f"**Tags:** {', '.join(self.tags)}")

        if self.dependencies:
            lines.append(f"**Dependencies:** {', '.join(self.dependencies)}")

        lines.append("")
        lines.append("**Acceptance Criteria:**")
        for ac in self.acceptance_criteria:
            lines.append(f"- {ac.description}")

        if self.edge_cases:
            lines.append("")
            lines.append("**Edge Cases:**")
            for ec in self.edge_cases:
                lines.append(f"- ⚠️ {ec}")

        if self.technical_notes:
            lines.append("")
            lines.append("**Technical Notes:**")
            for note in self.technical_notes:
                lines.append(f"- 🔧 {note}")

        return "\n".join(lines)

    def to_jira_format(self) -> dict:
        """Format for JIRA issue creation API."""
        description_parts = [self.description, ""]

        if self.acceptance_criteria:
            description_parts.append("h3. Acceptance Criteria")
            for ac in self.acceptance_criteria:
                description_parts.append(f"* {ac.description}")

        if self.edge_cases:
            description_parts.append("")
            description_parts.append("h3. Edge Cases")
            for ec in self.edge_cases:
                description_parts.append(f"* {ec}")

        if self.technical_notes:
            description_parts.append("")
            description_parts.append("h3. Technical Notes")
            for note in self.technical_notes:
                description_parts.append(f"* {note}")

        if self.test_scenarios:
            description_parts.append("")
            description_parts.append("h3. QA Scenarios")
            for scenario in self.test_scenarios:
                # Wrap in code block for better Jira formatting
                clean_scenario = scenario.replace("```gherkin", "").replace("```", "").strip()
                description_parts.append("{code:gherkin}\n" + clean_scenario + "\n{code}")

        return {
            "summary": self.title,
            "description": "\n".join(description_parts),
            "labels": self.tags,
        }


class Epic(BaseModel):
    """
    The input epic being decomposed.

    Captures the original user request along with any additional context.

    Example:
        Epic(
            title="SSO Login Support",
            description="We need to add SSO login support for enterprise customers",
            context="We use Azure AD as our IdP. Need SAML and OIDC support."
        )
    """

    title: str = Field(..., description="Short epic title", max_length=100)
    description: str = Field(..., description="Full epic description")
    context: str | None = Field(
        None,
        description="Additional context (tech stack, constraints, etc.)",
    )
    project_key: str | None = Field(
        None,
        description="The JIRA project key associated with this epic",
    )
    business_value: str | None = Field(
        None,
        description="Why this epic matters to the business",
    )
    stakeholders: list[str] = Field(
        default_factory=list,
        description="Key stakeholders for this epic",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags for the initiative",
    )
    test_scenarios: list[str] = Field(
        default_factory=list,
        description="High-level Business Success Scenarios (Gherkin). Focus on E2E journeys and SIT/BAT validation.",
    )

    def to_jira_format(self) -> dict:
        """Format epic for JIRA export."""
        description_parts = [self.description]

        if self.context:
            description_parts.append("")
            description_parts.append("h3. Context")
            description_parts.append(self.context)

        if self.business_value:
            description_parts.append("")
            description_parts.append("h3. Business Value")
            description_parts.append(self.business_value)

        if self.stakeholders:
            description_parts.append("")
            description_parts.append("h3. Stakeholders")
            for stakeholder in self.stakeholders:
                description_parts.append(f"* {stakeholder}")

        if self.test_scenarios:
            description_parts.append("")
            description_parts.append("h3. Business Success Scenarios (SIT/BAT)")
            for scenario in self.test_scenarios:
                clean_scenario = scenario.replace("```gherkin", "").replace("```", "").strip()
                description_parts.append("{code:gherkin}\n" + clean_scenario + "\n{code}")

        return {
            "summary": self.title,
            "description": "\n".join(description_parts).strip(),
            "labels": self.tags,
        }


class DecompositionResult(BaseModel):
    """
    The full decomposition output containing epic and all stories.

    This is the primary response model returned by the agent.

    Example:
        result = DecompositionResult(
            epic=Epic(...),
            stories=[UserStory(...), ...],
            summary="Decomposed into 5 user stories covering authentication flow..."
        )
    """

    epic: Epic = Field(..., description="The decomposed epic")
    stories: list[UserStory] = Field(
        default_factory=list,
        description="List of decomposed user stories",
    )
    conversation_title: str | None = Field(
        None,
        description="Smart title for this conversation (3-5 words)",
    )
    summary: str = Field(
        ...,
        description="Brief summary of the decomposition",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Suggestions for the team (dependencies, risks, etc.)",
    )
    total_estimated_effort: str | None = Field(
        None,
        description="Aggregate effort estimate if complexity provided",
    )
    suggested_sprint_distribution: list[dict] | None = Field(
        None,
        description="Suggested sprint groupings based on dependencies",
    )

    def to_markdown(self) -> str:
        """Format full result as markdown document."""
        lines = [
            f"# {self.epic.title}",
            "",
            f"**Description:** {self.epic.description}",
            "",
        ]

        if self.epic.context:
            lines.append(f"**Context:** {self.epic.context}")
            lines.append("")

        lines.append(f"**Summary:** {self.summary}")
        lines.append("")

        if self.total_estimated_effort:
            lines.append(f"**Total Estimated Effort:** {self.total_estimated_effort}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## User Stories")
        lines.append("")

        for story in self.stories:
            lines.append(story.to_markdown())
            lines.append("")
            lines.append("---")
            lines.append("")

        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for rec in self.recommendations:
                lines.append(f"- 💡 {rec}")

        return "\n".join(lines)

    def get_story_by_id(self, story_id: str) -> UserStory | None:
        """Find a story by its ID."""
        for story in self.stories:
            if story.id == story_id:
                return story
        return None

    def get_stories_by_tag(self, tag: str) -> list[UserStory]:
        """Get all stories with a specific tag."""
        return [s for s in self.stories if tag in s.tags]

    def get_dependency_order(self) -> list[str]:
        """Get story IDs in dependency order (simple topological sort)."""
        # Stories with no dependencies first
        ordered = []
        remaining = {s.id: set(s.dependencies) for s in self.stories}

        while remaining:
            # Find stories with no unmet dependencies
            ready = [sid for sid, deps in remaining.items() if not deps - set(ordered)]
            if not ready:
                # Circular dependency or missing - add remaining in order
                ready = list(remaining.keys())
            ordered.extend(sorted(ready))
            for sid in ready:
                del remaining[sid]

        return ordered
