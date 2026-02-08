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

        # Handle help response (from HelpNode)
        help_response = state.get("help_response")
        if help_response:
            logger.info("FormatNode: Formatting help response")
            messages = state.get("messages", [])
            messages = messages + [{"role": "assistant", "content": help_response}]
            return {
                "formatted_output": help_response,
                "summary": "Backlog Assistant capabilities and help guide",
                "messages": messages,
                "error": None,
            }

        # Handle grooming report (from GroomNode)
        grooming_report = state.get("grooming_report")
        if grooming_report:
            logger.info("FormatNode: Formatting grooming report")
            report_text = self._format_grooming_report(grooming_report)
            messages = state.get("messages", [])
            messages = messages + [{"role": "assistant", "content": report_text}]
            return {
                "formatted_output": report_text,
                "summary": "Backlog grooming and quality analysis report",
                "messages": messages,
                "error": None,
            }

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

            # Add assistant message to history (Ensure JIRA links are included if recently exported)
            messages = state.get("messages", [])
            if current_result and current_result.summary:
                assistant_content = current_result.summary

                # If we just performed an export, the summary might be empty or generic.
                # FormatNode appends export details to formatted_output; we should also add to message.
                if export_result:
                    assistant_content += f"\n\n{export_result.get('message', '')}"
                    issues = export_result.get("issues", [])
                    if issues:
                        assistant_content += "\n\n**Created JIRA Issues:**\n"
                        for issue in issues:
                            assistant_content += (
                                f"- [{issue.get('jira_key')}]({issue.get('url')}) - {issue.get('summary', '')}\n"
                            )

                messages = messages + [{"role": "assistant", "content": assistant_content}]

            return {
                "formatted_output": formatted,
                "messages": messages,
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
                summary = issue.get("summary", "")
                confirmation += f"- **[{key}]({url})** - {summary}\n"

        return formatted + confirmation

    def _format_json(self, result: DecompositionResult) -> str:
        """Format as pretty-printed JSON."""
        return result.model_dump_json(indent=2)

    def _format_markdown(self, result: DecompositionResult) -> str:
        """Format as markdown document."""
        return result.to_markdown()

    def _format_grooming_report(self, report: dict) -> str:
        """Format grooming report as markdown."""
        if report.get("error"):
            return f"## ⚠️ Grooming Error\n\n{report['error']}"
        
        output = "## 📊 Backlog Grooming Report\n\n"
        output += f"**Summary**: {report.get('summary', 'N/A')}\n\n"
        
        total = report.get("total_stories", 0)
        if total:
            output += f"📋 **Total Stories Analyzed**: {total}\n\n"
        
        duplicates = report.get("duplicates", [])
        if duplicates:
            output += "### 🔁 Potential Duplicates\n"
            for dup in duplicates:
                if isinstance(dup, dict):
                    s1, s2 = dup.get("story_1", "?"), dup.get("story_2", "?")
                    sim = dup.get("similarity", 0)
                    reason = dup.get("reason", "")
                    output += f"- `{s1}` ↔ `{s2}` ({int(sim * 100)}%): {reason}\n"
                else:
                    output += f"- {dup}\n"
            output += "\n"
        else:
            output += "✅ **No duplicates detected**\n\n"
        
        dependencies = report.get("dependencies", [])
        if dependencies:
            output += "### 🔗 Dependencies\n"
            for dep in dependencies:
                if isinstance(dep, dict):
                    story, depends, dep_type = dep.get("story", "?"), dep.get("depends_on", "?"), dep.get("type", "requires")
                    reason = dep.get("reason", "")
                    output += f"- `{story}` → `{depends}` ({dep_type}): {reason}\n"
                else:
                    output += f"- {dep}\n"
            output += "\n"
        
        quality_issues = report.get("quality_issues", [])
        if quality_issues:
            # Group by severity
            high = [q for q in quality_issues if q.get("severity") == "high"]
            medium = [q for q in quality_issues if q.get("severity") == "medium"]
            low = [q for q in quality_issues if q.get("severity") == "low"]
            
            output += "### ⚠️ Quality Issues\n"
            
            if high:
                output += "\n**🔴 High Priority:**\n"
                for issue in high:
                    output += f"- `{issue.get('story', '?')}`: {issue.get('issue', '?')} - {issue.get('suggestion', '')}\n"
            
            if medium:
                output += "\n**🟡 Medium Priority:**\n"
                for issue in medium:
                    output += f"- `{issue.get('story', '?')}`: {issue.get('issue', '?')} - {issue.get('suggestion', '')}\n"
            
            if low:
                output += "\n**🟢 Low Priority:**\n"
                for issue in low:
                    output += f"- `{issue.get('story', '?')}`: {issue.get('issue', '?')}\n"
            
            output += "\n"
        else:
            output += "✅ **All stories meet quality standards**\n\n"
        
        priority_suggestions = report.get("priority_suggestions", [])
        if priority_suggestions:
            output += "### 🎯 Priority Suggestions\n"
            for sug in priority_suggestions[:5]:  # Limit to top 5
                if isinstance(sug, dict):
                    story = sug.get("story", "?")
                    current = sug.get("current", "N/A")
                    suggested = sug.get("suggested", "?")
                    reason = sug.get("reason", "")
                    output += f"- `{story}`: {current} → **{suggested}** ({reason})\n"
            if len(priority_suggestions) > 5:
                output += f"_...and {len(priority_suggestions) - 5} more suggestions_\n"
            output += "\n"
        
        return output

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
