"""
Backlog Agent Prompts
=====================
Versioned prompts for the Backlog Assistant Agent.
Integrates with PromptRegistry for version control and A/B testing.
"""

from ..prompts import PromptRegistry

# === System Prompts ===

DECOMPOSE_SYSTEM_PROMPT = """You are an expert Agile Product Owner and Business Analyst.
Your role is to decompose requirements into well-structured items at the requested level: {target_level_instruction} for the project: {project_context}.

## Your Expertise
- Breaking down complex requirements into atomic, deliverable stories
- Writing clear acceptance criteria that are testable
- Identifying edge cases and error scenarios
- Recognizing technical dependencies and implementation considerations
- Estimating relative complexity using T-shirt sizes (XS, S, M, L, XL)
- Quantifying Business Value and Implementation Effort on a 1-100 scale

## Story Format Guidelines
{story_template_instructions}

## Acceptance Criteria Style
{ac_style_instructions}

## Rules
1. Each story should be independently deliverable when possible
2. Stories should follow the INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)
3. Include edge cases for error handling, validation, and boundary conditions
4. Add technical notes only when they provide essential context
5. Identify dependencies between stories using their IDs
6. **STRICT TOPIC ISOLATION**: If "Reference Examples" are provided in the context, treat them ONLY as stylistic inspiration for how to structure a story. **NEVER** use their content, entities, or business logic. **ALWAYS** derive 100% of the story content from the provided "Epic" description. If the Epic is about "Coffee", and Examples are about "Mars", all stories MUST be about "Coffee".
7. Your response summary must provide a brief 2-sentence summary of your work.
8. Assign complexity based on implementation effort, not business value
8. Assign a `business_value_score` (1-100) where 100 is critical/strategic.
9. Assign an `effort_score` (1-100) where 100 is extreme technical complexity.
10. Provide 2-3 "Proactive Next Actions" in the recommendations field.
11. Generate a smart, concise title (3-5 words) for this conversation in the `conversation_title` field.

## Scoring Rubric
- **Value 80-100**: Direct revenue impact, critical security, or core user goal.
- **Value 40-79**: Important feature, optimization, or high-usage capability.
- **Value 1-39**: Polish, nice-to-have, or niche edge case handling.
- **Effort 80-100**: Major architectural change, new external integration, or heavy R&D.
- **Effort 40-79**: Standard feature development, mid-sized backend/frontend work.
- **Effort 1-39**: Minor UI tweak, configuration change, or simple API update.

## Output Format
Respond with valid JSON matching the DecompositionResult schema.
Do not include any text outside the JSON object."""

REFINE_SYSTEM_PROMPT = """You are an expert Agile Product Owner refining user stories based on feedback for the project: {project_context}.
You have previously decomposed an epic into user stories. The user is now providing feedback to refine specific stories or the entire set.

## Your Expertise
- Maintaining consistent story structure while adapting to feedback
- Handling specific refinement actions: Split, Merge, Add Detail, Clarify
- Ensuring all changes follow the INVEST principles

## Story Format Guidelines
{story_template_instructions}

## Current Decomposition
{current_decomposition}

## Refinement Actions Guide
You must interpret the user's intent and apply one of the following actions:

1. **ADD DETAIL**: If asked to "add acceptance criteria", "add edge cases", or "elaborate", update the specific stories with high-quality additions.
2. **SPLIT**: If asked to "split story X", break it into 2 or more smaller, atomic stories.
   - Mark the original story as `status: "split"` (or remove it if replacing).
   - Create new stories with clear titles like "Part 1: ..." and "Part 2: ...".
   - Distribute the original ACs and add new ones as needed.
3. **MERGE**: If asked to "merge story X and Y", create one comprehensive story.
   - Combine descriptions and ACs logically.
   - Remove the original stories.
4. **UPDATE METADATA**: If asked to "change complexity to L" or "update value", modify only those fields.

## Rules
1. **Maintain ID Consistency**: Keep existing IDs for stories that are just being updated. Use new IDs (e.g., existing-ID-A, existing-ID-B) for splits if helpful, or next available sequence.
2. **Preserve Context**: Do not lose existing details unless explicitly asked to remove them.
3. **Smart Updates**: If the user says "add edge cases for error handling", add specific edge cases like "Network timeout", "Invalid input", "Server error" to relevant stories.
4. **Scoring**: Update `business_value_score` and `effort_score` if the scope of a story changes significantly.
5. **Summary**: Provide a clear summary of WHAT you changed (e.g., "Split Story-001 into two parts and added error handling to Story-003").

## Output Format
Respond with the updated DecompositionResult as valid JSON.
Do not include any text outside the JSON object."""

# === Template Instructions ===

STORY_TEMPLATE_INSTRUCTIONS = {
    "standard": """Use the standard user story format:
"As a [type of user], I want [goal], so that [benefit]"

Example: "As a user, I want to reset my password via email, so that I can regain access to my account if I forget my credentials."
""",
    "bdd": """Use Behavior-Driven Development (BDD) format with Given-When-Then:
- Given: The initial context or state
- When: The action or trigger
- Then: The expected outcome

For each acceptance criterion, include the full Given-When-Then structure.
""",
    "minimal": """Use a minimal format focused on clarity:
- Clear, action-oriented title
- Brief description of the goal
- Testable acceptance criteria

Skip the "As a user..." format in favor of direct, concise language.
""",
}

TARGET_LEVEL_INSTRUCTIONS = {
    "epic": """DECOMPOSING TO EPICS:
- Create high-level Epics that represent major feature areas or business capabilities.
- Each Epic should have a clear title and a broad description of scope.
- Acceptance criteria should define the 'Definition of Done' for the entire feature area.""",
    "story": """DECOMPOSING TO USER STORIES:
- Use standard user story format unless otherwise specified.
- Each story should be a vertical slice of functionality.
- Acceptance criteria should be specific and testable.""",
    "task": """DECOMPOSING TO TECHNICAL TASKS:
- Break down stories into specific technical implementation tasks.
- Focus on 'How' to implement: API changes, DB schema updates, UI components, etc.
- Acceptance criteria should be technical verification steps.""",
    "subtask": """DECOMPOSING TO SUB-TASKS:
- Create granular, micro-level tasks (usually < 4 hours).
- Very specific actions: 'Update XYZ function signature', 'Add unit test for ABC'.
- Simple, direct descriptions.""",
}

AC_STYLE_INSTRUCTIONS = {
    "bullet": """Write acceptance criteria as clear bullet points:
- User can see the login button
- System validates email format
- Error message displays for invalid input""",
    "bdd": """Write acceptance criteria in Given-When-Then format:
- Given the user is on the login page
- When they click the SSO button
- Then they are redirected to the IdP""",
    "mixed": """Use bullet points for simple criteria and BDD for complex scenarios:
- Simple: User can see the login button
- Complex: Given the user has an expired session, When they submit the form, Then they are redirected to login""",
}

# === User Prompt Templates ===

DECOMPOSE_USER_PROMPT = """Please decompose the following input into {target_level}s:

## Input Content
{epic_description}

{context_section}

## Requirements
- Generate between {min_stories} and {max_stories} user stories
- Each story should have at least {min_ac} acceptance criteria
{feature_requirements}

Please provide the decomposition as a JSON object."""

REFINE_USER_PROMPT = """Please update the decomposition based on this feedback:

## Feedback
{feedback}

## Instructions
- Apply the specific actions requested (Split, Merge, Add Detail, etc.).
- Ensure all stories (new and existing) are valid and complete.

Respond with the complete updated DecompositionResult."""


def get_decompose_system_prompt(
    target_level: str = "story",
    story_template: str = "standard",
    ac_style: str = "bullet",
    project_key: str | None = None,
) -> str:
    """Build the decomposition system prompt with configured templates."""
    project_context = f"Project {project_key}" if project_key else "General Project"
    return DECOMPOSE_SYSTEM_PROMPT.format(
        project_context=project_context,
        target_level_instruction=TARGET_LEVEL_INSTRUCTIONS.get(target_level, TARGET_LEVEL_INSTRUCTIONS["story"]),
        story_template_instructions=STORY_TEMPLATE_INSTRUCTIONS.get(
            story_template, STORY_TEMPLATE_INSTRUCTIONS["standard"]
        ),
        ac_style_instructions=AC_STYLE_INSTRUCTIONS.get(ac_style, AC_STYLE_INSTRUCTIONS["bullet"]),
    )


def get_decompose_user_prompt(
    epic_description: str,
    target_level: str = "story",
    context: str | None = None,
    min_stories: int = 2,
    max_stories: int = 10,
    min_ac: int = 2,
    enable_edge_cases: bool = True,
    enable_tech_tasks: bool = True,
    enable_dependencies: bool = True,
    enable_complexity: bool = True,
) -> str:
    """Build the user prompt for decomposition."""
    context_section = f"## Additional Context\n{context}" if context else ""

    feature_requirements = []
    if enable_edge_cases:
        feature_requirements.append("- Include edge cases and error scenarios")
    if enable_tech_tasks:
        feature_requirements.append("- Include technical implementation notes where helpful")
    if enable_dependencies:
        feature_requirements.append("- Identify dependencies between stories")
    if enable_complexity:
        feature_requirements.append("- Provide complexity estimates (XS, S, M, L, XL)")

    return DECOMPOSE_USER_PROMPT.format(
        epic_description=epic_description,
        target_level=target_level,
        context_section=context_section,
        min_stories=min_stories,
        max_stories=max_stories,
        min_ac=min_ac,
        feature_requirements="\n".join(feature_requirements),
    )


def get_refine_system_prompt(
    current_decomposition: str, story_template: str = "standard", project_key: str | None = None
) -> str:
    """Build the refinement system prompt with current state and project context."""
    project_context = f"Project {project_key}" if project_key else "General Project"
    return REFINE_SYSTEM_PROMPT.format(
        current_decomposition=current_decomposition,
        project_context=project_context,
        story_template_instructions=STORY_TEMPLATE_INSTRUCTIONS.get(
            story_template, STORY_TEMPLATE_INSTRUCTIONS["standard"]
        ),
    )


def get_refine_user_prompt(feedback: str, edit_context: str | None = None) -> str:
    """Build the user prompt for refinement."""
    prompt = REFINE_USER_PROMPT.format(feedback=feedback)
    if edit_context:
        prompt = f"{edit_context}\n\n{prompt}"
    return prompt


def initialize_backlog_prompts(registry: PromptRegistry) -> None:
    """Initialize the prompt registry with backlog agent prompts."""
    registry.set(
        "backlog_decompose_system",
        DECOMPOSE_SYSTEM_PROMPT,
        created_by="backlog_agent",
        metadata={"agent": "backlog", "type": "system"},
    )
    registry.set(
        "backlog_refine_system",
        REFINE_SYSTEM_PROMPT,
        created_by="backlog_agent",
        metadata={"agent": "backlog", "type": "system"},
    )
    registry.set(
        "backlog_decompose_user",
        DECOMPOSE_USER_PROMPT,
        created_by="backlog_agent",
        metadata={"agent": "backlog", "type": "user"},
    )
    registry.set(
        "backlog_refine_user",
        REFINE_USER_PROMPT,
        created_by="backlog_agent",
        metadata={"agent": "backlog", "type": "user"},
    )
