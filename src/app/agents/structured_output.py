"""
Structured Output Validation.
=============================
Ensures LLM responses conform to expected schemas with retry logic.

This module validates that tool calls and structured responses match
their expected Pydantic schemas, with automatic retry on failure.
"""

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .azure_openai import LLMService

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Raised when output cannot be validated to schema."""

    pass


class StructuredOutputValidator:
    """
    Validates LLM outputs against Pydantic schemas.

    Usage:
        validator = StructuredOutputValidator()

        class TaskOutput(BaseModel):
            task_name: str
            priority: int
            due_date: str

        # Validate a response
        result = validator.validate(llm_response, TaskOutput)

        # Or with retry
        result = await validator.with_retry(
            llm, prompt, TaskOutput, max_retries=3
        )
    """

    def validate(self, content: str, schema: type[T]) -> T:
        """
        Validate content against a Pydantic schema.

        Args:
            content: JSON string or dict from LLM
            schema: Pydantic model class to validate against

        Returns:
            Validated Pydantic model instance

        Raises:
            StructuredOutputError: If validation fails
        """
        try:
            # Handle string input
            if isinstance(content, str):
                # Try to parse as JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    data = self._extract_json(content)
            else:
                data = content

            # Validate against schema
            return schema.model_validate(data)

        except ValidationError as e:
            raise StructuredOutputError(f"Validation failed: {e}")
        except Exception as e:
            raise StructuredOutputError(f"Failed to parse output: {e}")

    def _extract_json(self, content: str) -> dict[str, Any]:
        """Extract JSON from markdown code blocks or raw text."""
        import re

        # 1. Try markdown code blocks first
        patterns = [
            r"```json\s*\n(.*?)\n```",
            r"```\s*\n(.*?)\n```",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    continue

        # 2. Try to find the outermost { } pair
        try:
            # Find the first { and the last }
            start = content.find("{")
            end = content.rfind("}")
            
            if start != -1 and end != -1 and end > start:
                json_str = content[start : end + 1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 3. Fallback to full string if no markers and steps 1 & 2 failed
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            raise ValueError(f"Could not extract valid JSON from content. Content starts with: {content[:100]}...")

    async def with_retry(
        self, llm: LLMService, prompt: str, schema: type[T], max_retries: int = 3, system_prompt: str | None = None
    ) -> T:
        """
        Call LLM with automatic retry on validation failure.

        Includes the schema in the prompt to guide the LLM.
        """
        schema_json = json.dumps(schema.model_json_schema(), indent=2)

        base_system = system_prompt or ""
        structured_system = f"""{base_system}

You must respond with valid JSON matching this schema:
{schema_json}

Do not include any text outside the JSON object."""

        last_error = None

        for attempt in range(max_retries):
            try:
                messages = [{"role": "system", "content": structured_system}, {"role": "user", "content": prompt}]

                if attempt > 0:
                    # Add error feedback for retries
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Previous response was invalid: {last_error}. Please try again with valid JSON.",
                        }
                    )

                response = await llm.chat(messages)
                validated_data = self.validate(response.content, schema)

                # Capture usage metadata if available (LangChain style)
                usage = getattr(response, "usage_metadata", {})

                return validated_data, usage

            except StructuredOutputError as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                continue

        raise StructuredOutputError(
            f"Failed to get valid output after {max_retries} attempts. Last error: {last_error}"
        )


class ToolCallValidator:
    """
    Validates tool/function calls from LLM.

    Usage:
        validator = ToolCallValidator()
        validator.register_tool("search", SearchParams)
        validator.register_tool("create_task", CreateTaskParams)

        # Validate a tool call
        tool_name, params = validator.validate_tool_call(llm_tool_call)
    """

    def __init__(self):
        self._tools: dict[str, type[BaseModel]] = {}

    def register_tool(self, name: str, schema: type[BaseModel]) -> None:
        """Register a tool with its parameter schema."""
        self._tools[name] = schema

    def list_tools(self) -> list[str]:
        """List registered tool names."""
        return list(self._tools.keys())

    def get_schema(self, name: str) -> type[BaseModel] | None:
        """Get schema for a tool."""
        return self._tools.get(name)

    def validate_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> BaseModel:
        """
        Validate tool call arguments against registered schema.

        Returns validated Pydantic model instance.
        """
        schema = self._tools.get(tool_name)
        if schema is None:
            raise StructuredOutputError(f"Unknown tool: {tool_name}")

        try:
            return schema.model_validate(arguments)
        except ValidationError as e:
            raise StructuredOutputError(f"Invalid arguments for {tool_name}: {e}")

    def get_tools_schema(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible tools schema for function calling."""
        tools = []
        for name, schema in self._tools.items():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": schema.__doc__ or f"Tool: {name}",
                        "parameters": schema.model_json_schema(),
                    },
                }
            )
        return tools
