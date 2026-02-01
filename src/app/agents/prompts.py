"""
Prompt Versioning.
==================
Version control for agent prompts with rollback capability.

Track prompt changes, A/B test variants, and roll back to previous versions.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PromptVersion(BaseModel):
    """A versioned prompt."""

    name: str
    version: int
    content: str
    content_hash: str
    metadata: dict[str, Any] = {}
    created_at: datetime
    created_by: str | None = None
    is_active: bool = True

    @classmethod
    def create(
        cls, name: str, content: str, version: int, created_by: str | None = None, metadata: dict | None = None
    ) -> "PromptVersion":
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return cls(
            name=name,
            version=version,
            content=content,
            content_hash=content_hash,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            created_by=created_by,
            is_active=True,
        )


class BasePromptStore(ABC):
    """Abstract base for prompt storage backends."""

    @abstractmethod
    async def save(self, prompt: PromptVersion) -> None:
        pass

    @abstractmethod
    async def get(self, name: str, version: int | None = None) -> PromptVersion | None:
        pass

    @abstractmethod
    async def list_versions(self, name: str) -> list[PromptVersion]:
        pass

    @abstractmethod
    async def delete(self, name: str, version: int) -> bool:
        pass


class InMemoryPromptStore(BasePromptStore):
    """In-memory prompt storage (for development/testing)."""

    def __init__(self):
        self._prompts: dict[str, dict[int, PromptVersion]] = {}

    async def save(self, prompt: PromptVersion) -> None:
        if prompt.name not in self._prompts:
            self._prompts[prompt.name] = {}
        self._prompts[prompt.name][prompt.version] = prompt

    async def get(self, name: str, version: int | None = None) -> PromptVersion | None:
        if name not in self._prompts:
            return None

        versions = self._prompts[name]
        if not versions:
            return None

        if version is not None:
            return versions.get(version)

        # Return latest active version
        active = [v for v in versions.values() if v.is_active]
        if not active:
            return None
        return max(active, key=lambda v: v.version)

    async def list_versions(self, name: str) -> list[PromptVersion]:
        if name not in self._prompts:
            return []
        return sorted(self._prompts[name].values(), key=lambda v: v.version, reverse=True)

    async def delete(self, name: str, version: int) -> bool:
        if name in self._prompts and version in self._prompts[name]:
            del self._prompts[name][version]
            return True
        return False


class PromptRegistry:
    """
    High-level prompt versioning service.

    Usage:
        registry = PromptRegistry()

        # Create/update a prompt
        registry.set("system_prompt", "You are a helpful assistant.")

        # Get the current version
        prompt = registry.get("system_prompt")

        # Get a specific version
        prompt_v2 = registry.get("system_prompt", version=2)

        # List all versions
        versions = registry.list_versions("system_prompt")

        # Rollback to previous version
        registry.rollback("system_prompt", version=1)
    """

    def __init__(self, store: BasePromptStore | None = None):
        self._store = store or InMemoryPromptStore()
        self._cache: dict[str, PromptVersion] = {}

    def set_store(self, store: BasePromptStore) -> None:
        """Switch storage backend."""
        self._store = store
        self._cache.clear()

    async def set(
        self, name: str, content: str, created_by: str | None = None, metadata: dict | None = None
    ) -> PromptVersion:
        """
        Create a new version of a prompt.

        Automatically increments version number.
        """
        # Get current latest version
        current = await self._store.get(name)
        new_version = (current.version + 1) if current else 1

        # Check if content actually changed
        if current and current.content == content:
            logger.debug(f"Prompt {name} unchanged, skipping version bump")
            return current

        prompt = PromptVersion.create(
            name=name, content=content, version=new_version, created_by=created_by, metadata=metadata
        )

        await self._store.save(prompt)
        self._cache[name] = prompt

        logger.info(f"Created prompt {name} v{new_version}")
        return prompt

    async def get(self, name: str, version: int | None = None, default: str | None = None) -> str | None:
        """
        Get prompt content.

        Returns the active version unless a specific version is requested.
        """
        # Check cache for latest
        if version is None and name in self._cache:
            return self._cache[name].content

        prompt = await self._store.get(name, version)

        if prompt is None:
            return default

        # Update cache with latest
        if version is None:
            self._cache[name] = prompt

        return prompt.content

    async def get_prompt(self, name: str, version: int | None = None) -> PromptVersion | None:
        """Get full prompt version object."""
        return await self._store.get(name, version)

    async def list_versions(self, name: str) -> list[PromptVersion]:
        """List all versions of a prompt."""
        return await self._store.list_versions(name)

    async def rollback(self, name: str, version: int, created_by: str | None = None) -> PromptVersion:
        """
        Rollback to a previous version.

        Creates a new version with the content from the specified version.
        """
        old = await self._store.get(name, version)
        if old is None:
            raise ValueError(f"Version {version} not found for prompt {name}")

        return await self.set(
            name=name, content=old.content, created_by=created_by, metadata={"rollback_from": version}
        )

    async def delete(self, name: str, version: int) -> bool:
        """Delete a specific version."""
        result = await self._store.delete(name, version)

        if name in self._cache and self._cache[name].version == version:
            del self._cache[name]

        return result

    async def compare(self, name: str, version_a: int, version_b: int) -> dict[str, Any]:
        """Compare two versions of a prompt."""
        a = await self._store.get(name, version_a)
        b = await self._store.get(name, version_b)

        if a is None or b is None:
            raise ValueError("One or both versions not found")

        return {
            "name": name,
            "version_a": version_a,
            "version_b": version_b,
            "content_a": a.content,
            "content_b": b.content,
            "changed": a.content != b.content,
            "a_created_at": a.created_at.isoformat(),
            "b_created_at": b.created_at.isoformat(),
        }

    def list_names(self) -> list[str]:
        """List all prompt names (from cache only)."""
        return list(self._cache.keys())


# Predefined prompts for agent bootstrap
DEFAULT_PROMPTS = {
    "doc_assistant_system": """You are a helpful document assistant. Your role is to:
1. Answer questions based on the retrieved documents
2. Cite your sources when providing information
3. Acknowledge when you don't have enough information
4. Be concise but thorough in your responses""",
    "summarization": """Summarize the following text concisely while preserving key information:

{text}

Summary:""",
    "rewrite_query": """Given the user's question, rewrite it to be more specific and searchable.
Keep the core intent but add relevant keywords.

Original: {query}
Rewritten:""",
}


async def initialize_default_prompts(registry: PromptRegistry) -> None:
    """Initialize registry with default prompts."""
    for name, content in DEFAULT_PROMPTS.items():
        existing = await registry.get(name)
        if existing is None:
            await registry.set(name, content, created_by="system")
            logger.info(f"Initialized default prompt: {name}")


# Global registry
prompt_registry = PromptRegistry()
