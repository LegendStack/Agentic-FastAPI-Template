"""
Format Node
===========
Format the decomposition output for the requested target.
Supports JSON, Markdown, and JIRA formats.
"""

import json
import logging
from typing import Any

from ..config import BacklogAgentConfig
from ..schemas import DecompositionResult
from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class FormatNode:
    """
    Format decomposition output for the requested format.

    Supports three output formats:
    - JSON: Raw structured data (default)
    - Markdown: Human-readable format for documentation
    - JIRA: Pre-formatted for JIRA issue creation

    Usage:
        node = FormatNode()
        updated_state = await node(state)
    """

    def __init__(self, config: BacklogAgentConfig | None = None):
        self.config = config or BacklogAgentConfig()

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Format the current result based on output_format.

        Args:
            state: Current agent state with current_result

        Returns:
            State update with formatted_output
        """
        logger.info("FormatNode: Formatting output")

        current_result = state.get("current_result")
        if not current_result:
            return {
                "error": state.get("error") or "No decomposition result to format",
                "is_first_message": not state.get("stories"),
                "is_export_requested": False,
            }

        # Convert from dict if needed
        if isinstance(current_result, dict):
            current_result = DecompositionResult.model_validate(current_result)

        output_format = state.get("output_format", self.config.DEFAULT_OUTPUT_FORMAT)

        try:
            if output_format == "markdown":
                formatted = self._format_markdown(current_result)
            elif output_format == "jira":
                formatted = self._format_jira(current_result)
            else:  # json
                formatted = self._format_json(current_result)

            logger.info(f"FormatNode: Formatted as {output_format}")

            # Add export result to formatted output if exists
            export_result = state.get("export_result")
            if export_result:
                formatted = self._append_export_confirmation(formatted, export_result)

            return {
                "formatted_output": formatted,
                "error": None,
            }

        except Exception as e:
            logger.error(f"FormatNode: Error - {e}")
            return {"error": f"Formatting failed: {str(e)}"}

    def _append_export_confirmation(self, formatted: str, export_result: dict[str, Any]) -> str:
        """Append JIRA save confirmation to the output."""
        status = export_result.get("status", "unknown")
        message = export_result.get("message", "")
        issues = export_result.get("issues", [])

        confirmation = f"\n\n---\n### 🚀 JIRA SAVE: {status.upper()}\n{message}\n\n"

        if issues:
            confirmation += "Created Issues:\n"
            for issue in issues:
                key = issue.get("jira_key", "N/A")
                url = issue.get("url", "#")
                confirmation += f"- **[{key}]({url})**\n"

        return formatted + confirmation

    def _format_json(self, result: DecompositionResult) -> str:
        """Format as pretty-printed JSON."""
        return result.model_dump_json(indent=2)

    def _format_markdown(self, result: DecompositionResult) -> str:
        """Format as markdown document."""
        return result.to_markdown()

    def _format_jira(self, result: DecompositionResult) -> str:
        """
        Format for JIRA import.

        Returns a JSON structure suitable for bulk JIRA issue creation.
        """
        jira_issues = []

        for story in result.stories:
            jira_format = story.to_jira_format()
            jira_issues.append(
                {
                    "fields": {
                        "project": {"key": self.config.JIRA_PROJECT_KEY or "PROJ"},
                        "issuetype": {"name": self.config.JIRA_ISSUE_TYPE},
                        "summary": jira_format["summary"],
                        "description": jira_format["description"],
                        "labels": jira_format["labels"],
                    },
                    "internalId": story.id,  # For reference
                    "dependencies": story.dependencies,
                    "complexity": story.estimated_complexity,
                }
            )

        output = {
            "epic": {
                "title": result.epic.title,
                "description": result.epic.description,
            },
            "issues": jira_issues,
            "metadata": {
                "total_stories": len(result.stories),
                "recommendations": result.recommendations,
            },
        }

        return json.dumps(output, indent=2)


# Convenience function for standalone testing
async def format_node(
    state: BacklogAgentState,
    config: BacklogAgentConfig | None = None,
) -> dict[str, Any]:
    """Functional wrapper for FormatNode."""
    node = FormatNode(config=config)
    return await node(state)
