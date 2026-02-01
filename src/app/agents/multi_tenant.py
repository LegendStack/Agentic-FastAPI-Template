"""
Multi-tenant support for RAG and agent workflows.
Provides tenant isolation, data filtering, and access control.
"""

import logging
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Context variable for current tenant (thread-safe)
current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)


class TenantContext(BaseModel):
    """Represents a tenant context for multi-tenant operations."""

    tenant_id: str
    tenant_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_sources: list[str] = Field(default_factory=list)
    max_documents: int = 10000
    is_active: bool = True


class TenantManager:
    """
    Manages tenant contexts for multi-tenant RAG operations.

    Usage:
        with tenant_manager.tenant_context("tenant-123"):
            # All RAG operations here will be filtered by tenant
            results = await vector_store.similarity_search(query_vec, filters=tenant_manager.get_filters())
    """

    def __init__(self):
        self._tenants: dict[str, TenantContext] = {}

    def register_tenant(self, tenant: TenantContext) -> None:
        """Register a new tenant."""
        self._tenants[tenant.tenant_id] = tenant
        logger.info(f"Registered tenant: {tenant.tenant_id}")

    def get_tenant(self, tenant_id: str) -> TenantContext | None:
        """Get a tenant by ID."""
        return self._tenants.get(tenant_id)

    def tenant_context(self, tenant_id: str):
        """Context manager for setting the current tenant."""
        return TenantContextManager(tenant_id)

    def get_current_tenant(self) -> str | None:
        """Get the current tenant from context."""
        return current_tenant.get()

    def get_filters(self) -> dict[str, Any]:
        """Get RAG filters for the current tenant."""
        tenant_id = self.get_current_tenant()
        if tenant_id:
            return {"tenant_id": tenant_id}
        return {}

    def validate_access(self, tenant_id: str, source_id: str) -> bool:
        """Validate if a tenant has access to a specific source."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        if not tenant.is_active:
            return False
        if tenant.allowed_sources and source_id not in tenant.allowed_sources:
            return False
        return True


class TenantContextManager:
    """Context manager for tenant isolation."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token = None

    def __enter__(self):
        self.token = current_tenant.set(self.tenant_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        current_tenant.reset(self.token)
        return False

    async def __aenter__(self):
        self.token = current_tenant.set(self.tenant_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        current_tenant.reset(self.token)
        return False


class MultiTenantVectorStore:
    """
    Wrapper that adds tenant isolation to any BaseVectorStore implementation.
    """

    def __init__(self, base_store, tenant_manager: TenantManager):
        self.base_store = base_store
        self.tenant_manager = tenant_manager

    async def add_documents(self, documents: list[dict[str, Any]], ids: list[str] | None = None) -> list[str]:
        """Add documents with automatic tenant tagging."""
        tenant_id = self.tenant_manager.get_current_tenant()

        if not tenant_id:
            raise ValueError("No tenant context set. Use tenant_manager.tenant_context().")

        # Inject tenant_id into all documents
        for doc in documents:
            doc["tenant_id"] = tenant_id

        return await self.base_store.add_documents(documents, ids)

    async def similarity_search(
        self, query_vector: list[float], k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Search with automatic tenant filtering."""
        tenant_filters = self.tenant_manager.get_filters()

        # Merge user filters with tenant filters
        combined_filters = {**(filters or {}), **tenant_filters}

        return await self.base_store.similarity_search(query_vector, k, combined_filters)

    async def delete_documents(self, ids: list[str]) -> None:
        """Delete documents (tenant validation should be done at API layer)."""
        return await self.base_store.delete_documents(ids)


# Global tenant manager instance
tenant_manager = TenantManager()
