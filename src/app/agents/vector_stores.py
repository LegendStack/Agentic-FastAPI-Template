from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security_utils import TenantEncryption

from ..models.agentic import DocumentSection
from .base import BaseVectorStore


class PgVectorStore(BaseVectorStore):
    """PostgreSQL implementation of the Vector Store using pgvector."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_documents(self, documents: list[dict[str, Any]], ids: list[str] | None = None) -> list[str]:
        """
        Expects documents as: [{'content': '...', 'embedding': [...], 'metadata': {...}, 'source_id': '...'}]
        """
        new_sections = []
        for doc in documents:
            section = DocumentSection(
                content=doc["content"],
                embedding=doc["embedding"],
                metadata_json=doc.get("metadata", {}),
                source_id=doc.get("source_id"),
                tenant_id=doc.get("tenant_id"),
            )
            new_sections.append(section)

        self.db.add_all(new_sections)
        await self.db.commit()
        return [str(s.id) for s in new_sections]

    async def similarity_search(
        self, query_vector: list[float], k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Perform cosine similarity search.
        Filters can be used to isolate tenants or sources.
        """
        # Cosine distance: 1 - cosine_similarity
        query = sa.select(DocumentSection).order_by(DocumentSection.embedding.cosine_distance(query_vector)).limit(k)

        # Apply filters (basic equality for now)
        if filters:
            for key, value in filters.items():
                if hasattr(DocumentSection, key):
                    query = query.where(getattr(DocumentSection, key) == value)

        result = await self.db.execute(query)
        sections = result.scalars().all()

        return [
            {
                "id": s.id,
                "content": TenantEncryption.decrypt(s.content, s.tenant_id)
                if s.metadata_json.get("encrypted")
                else s.content,
                "metadata": s.metadata_json,
                "source_id": s.source_id,
                "tenant_id": s.tenant_id,
            }
            for s in sections
        ]

    async def delete_documents(self, ids: list[str]) -> None:
        stmt = sa.delete(DocumentSection).where(DocumentSection.id.in_(ids))
        await self.db.execute(stmt)
        await self.db.commit()


class VectorStoreFactory:
    """Produces the correct vector store implementation based on config."""

    @staticmethod
    def get_store(db: AsyncSession) -> BaseVectorStore:
        from ..core.config import RAGBackend, settings

        if settings.RAG_BACKEND == RAGBackend.PGVECTOR:
            return PgVectorStore(db)
        elif settings.RAG_BACKEND == RAGBackend.AZURE_SEARCH:
            from .azure_search import AzureAISearchStore

            if not settings.AZURE_SEARCH_ENDPOINT or not settings.AZURE_SEARCH_KEY:
                raise ValueError("Azure AI Search credentials not configured.")

            return AzureAISearchStore(
                endpoint=settings.AZURE_SEARCH_ENDPOINT,
                api_key=settings.AZURE_SEARCH_KEY.get_secret_value(),
                index_name=settings.AZURE_SEARCH_INDEX_NAME,
            )
        else:
            raise ValueError(f"Unknown RAG backend: {settings.RAG_BACKEND}")
