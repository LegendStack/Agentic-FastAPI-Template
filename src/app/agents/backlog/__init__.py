"""
Backlog Assistant Agent
=======================
A state-of-the-art Story Decomposition Agent that breaks down high-level
epics into well-structured user stories with acceptance criteria.

Features:
- Conversational refinement via multi-turn chat
- Structured output with Pydantic validation
- Multiple output formats (JSON, Markdown, JIRA)
- Optional JIRA export integration
- Configurable story templates (standard, BDD, minimal)

Usage:
    from app.agents.backlog import BacklogAssistantAgent, BacklogAgentConfig

    # Basic usage with defaults
    agent = BacklogAssistantAgent()
    result = await agent.decompose("Add SSO login support for enterprise customers")

    # With configuration
    config = BacklogAgentConfig(ENABLE_EDGE_CASES=True, STORY_TEMPLATE="bdd")
    agent = BacklogAssistantAgent(config=config)

    # Conversational refinement
    result = await agent.chat(thread_id="abc123", message="Add more edge cases")
"""

from .backlog_agent import BacklogAssistantAgent
from .config import BacklogAgentConfig
from .schemas import (
    AcceptanceCriteria,
    DecompositionResult,
    Epic,
    UserStory,
)

__all__ = [
    "BacklogAssistantAgent",
    "BacklogAgentConfig",
    "AcceptanceCriteria",
    "DecompositionResult",
    "Epic",
    "UserStory",
]
