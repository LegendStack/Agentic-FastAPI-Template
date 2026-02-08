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

    async def similarity_search_hybrid(
        self, query: str, query_vector: list[float], k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Combine Vector Search with PostgreSQL Full Text Search.
        """
        # 1. Get Vector Results (Top K)
        vector_docs = await self.similarity_search(query_vector, k=k, filters=filters)

        # 2. Get Keyword Results (Top K) via TSVector
        # Using simple 'english' configuration.
        ts_query = (
            sa.select(DocumentSection)
            .where(sa.func.to_tsvector("english", DocumentSection.content).match(query))
            .limit(k)
        )

        if filters:
            for key, value in filters.items():
                if hasattr(DocumentSection, key):
                    ts_query = ts_query.where(getattr(DocumentSection, key) == value)

        result = await self.db.execute(ts_query)
        keyword_secs = result.scalars().all()

        keyword_docs = [
            {
                "id": s.id,
                "content": TenantEncryption.decrypt(s.content, s.tenant_id)
                if s.metadata_json.get("encrypted")
                else s.content,
                "metadata": s.metadata_json,
                "source_id": s.source_id,
                "tenant_id": s.tenant_id,
                "score": 1.0,  # Placeholder score
            }
            for s in keyword_secs
        ]

        # 3. Merge Strategies (Simple RRF-like or Union)
        # Map ID -> Doc
        merged = {}

        # Add Vector Docs (weight 0.7)
        for i, doc in enumerate(vector_docs):
            doc["score"] = 0.7 * (1 - (i / k))  # Simple rank decay
            merged[doc["id"]] = doc

        # Add Keyword Docs (weight 0.3)
        for i, doc in enumerate(keyword_docs):
            if doc["id"] in merged:
                merged[doc["id"]]["score"] += 0.3 * (1 - (i / k))
                merged[doc["id"]]["metadata"]["match_type"] = "hybrid"
            else:
                doc["score"] = 0.3 * (1 - (i / k))
                doc["metadata"]["match_type"] = "keyword"
                merged[doc["id"]] = doc

        # Sort by Score
        sorted_docs = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)
        return sorted_docs[:k]


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
        elif settings.RAG_BACKEND == RAGBackend.REDIS:
            from .redis_store import RedisVectorStore

            if not settings.REDIS_VECTOR_URL:
                raise ValueError("Redis Vector Store URL (REDIS_VECTOR_URL) not configured.")

            return RedisVectorStore(
                redis_url=settings.REDIS_VECTOR_URL,
                index_name=settings.REDIS_VECTOR_INDEX_NAME,
            )
        else:
            raise ValueError(f"Unknown RAG backend: {settings.RAG_BACKEND}")
